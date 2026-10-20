"""Opt-in Google Drive PDF saving, scoped to one configured folder.

The public PDF website never receives a service-account credential.
Cloud upload requires a separate staff save code so strangers cannot
exhaust a Google Drive quota by generating PDFs on a public site.
Supports both lightweight REST upload via requests and googleapiclient.
"""
import hmac
import io
import json
import os
import re
from pathlib import Path


class DriveConfigurationError(RuntimeError):
    pass


def enabled():
    return os.environ.get("GOOGLE_DRIVE_SAVE_ENABLED", "0") == "1"


def configuration_issue():
    """Return a safe error code, never any environment variable value."""
    if not enabled():
        return "save_enabled_not_1"
    if not os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"):
        return "service_account_json_missing"
    folder = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
    full = os.environ.get("GOOGLE_DRIVE_FULL_FOLDER_ID", "")
    mini = os.environ.get("GOOGLE_DRIVE_MINI_FOLDER_ID", "")
    if not folder and not (full and mini):
        return "parent_or_two_catalogue_folder_ids_missing"
    for folder_id in (folder, full, mini):
        if folder_id and not re.fullmatch(r"[A-Za-z0-9_-]{10,160}", folder_id):
            return "folder_id_invalid_format"
    if len(_owner_save_token()) < 16:
        return "save_token_missing_or_too_short"
    return None


def configured():
    return configuration_issue() is None


def _owner_save_token():
    # Reuse the existing private NUNES batch owner token if an independent
    # Drive code is not configured; never allow the public website to upload
    # anonymously or reveal credentials to the browser.
    return os.environ.get("GOOGLE_DRIVE_SAVE_TOKEN") or os.environ.get("NUNES_BATCH_TOKEN", "")


def authorized(code):
    expected = _owner_save_token()
    return len(expected) >= 16 and isinstance(code, str) and hmac.compare_digest(expected, code)


class _DriveRestClient:
    """Lightweight REST client for Google Drive v3 without heavy discovery cache."""
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}

    def get_or_create_folder(self, folder_name: str, parent: str) -> str:
        import requests
        safe_name = folder_name.replace("'", "\\'")
        query = (f"name = '{safe_name}' and "
                 f"mimeType = 'application/vnd.google-apps.folder' and "
                 f"'{parent}' in parents and trashed = false")
        url = "https://www.googleapis.com/drive/v3/files"
        params = {
            "q": query,
            "fields": "nextPageToken,files(id,name)",
            "pageSize": 30,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true"
        }
        r = requests.get(url, headers=self.headers, params=params, timeout=20)
        if r.status_code == 200:
            for entry in r.json().get("files", []):
                ident = str(entry.get("id") or "")
                if entry.get("name") == folder_name and re.fullmatch(r"[A-Za-z0-9_-]{10,160}", ident):
                    return ident

        create_url = "https://www.googleapis.com/drive/v3/files?supportsAllDrives=true"
        body = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent]
        }
        cr = requests.post(create_url, headers=self.headers, json=body, timeout=20)
        cr.raise_for_status()
        created_id = str(cr.json().get("id") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,160}", created_id):
            raise DriveConfigurationError("Google Drive failed to create catalogue folder.")
        return created_id

    def upload_pdf(self, filename: str, folder_id: str, data: bytes) -> dict:
        import requests
        metadata = {"name": filename, "parents": [folder_id]}
        boundary = "===============733083278152183144=="
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": f"multipart/related; boundary={boundary}"
        }
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=id,name,webViewLink"
        res = requests.post(url, headers=headers, data=body, timeout=40)
        res.raise_for_status()
        return res.json()


def _get_drive_client():
    from google.oauth2.service_account import Credentials
    import google.auth.transport.requests
    info = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"])
    creds = Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"])
    req = google.auth.transport.requests.Request()
    creds.refresh(req)
    return _DriveRestClient(creds.token)


def _destination_folder(client, kind):
    """Use explicit destination folder, else find/create catalog subfolder."""
    if kind not in ("full", "mini"):
        raise DriveConfigurationError("Invalid catalogue PDF type.")
    override_key = (
        "GOOGLE_DRIVE_FULL_FOLDER_ID" if kind == "full"
        else "GOOGLE_DRIVE_MINI_FOLDER_ID")
    explicit = os.environ.get(override_key, "")
    if explicit:
        return explicit
    parent = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "")
    if not parent:
        raise DriveConfigurationError("Catalogue destination folder unavailable.")
    folder_name = "Catalogue" if kind == "full" else "Mini Catalogue"
    
    if hasattr(client, "get_or_create_folder"):
        return client.get_or_create_folder(folder_name, parent)

    safe_name = folder_name.replace("'", "\\'")
    query = (f"name = '{safe_name}' and "
             f"mimeType = 'application/vnd.google-apps.folder' and "
             f"'{parent}' in parents and trashed = false")
    result = client.files().list(
        q=query, fields="nextPageToken,files(id,name)", page_size=30,
        supportsAllDrives=True, includeItemsFromAllDrives=True
    ).execute(num_retries=1)
    for entry in result.get("files", []):
        identifier = str(entry.get("id") or "")
        if entry.get("name") == folder_name and re.fullmatch(r"[A-Za-z0-9_-]{10,160}", identifier):
            return identifier
    created = client.files().create(
        body={"name": folder_name,
              "mimeType": "application/vnd.google-apps.folder",
              "parents": [parent]},
        fields="id,name", supportsAllDrives=True
    ).execute(num_retries=2)
    folder_id = str(created.get("id") or "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,160}", folder_id):
        raise DriveConfigurationError("Google Drive failed to create catalogue folder.")
    return folder_id


def save_pdf(path: Path, filename: str, token: str = "", kind: str = "full", allow_server_token: bool = False):
    """Return a Drive link only after an authorized successful upload."""
    if not configured():
        raise DriveConfigurationError("Google Drive saving has not been configured in Vercel.")
    expected = _owner_save_token()
    if not authorized(token):
        if allow_server_token and len(expected) >= 16:
            pass
        else:
            raise PermissionError("Invalid Drive save code.")
    filename = re.sub(r"[^a-zA-Z0-9 _().-]", "_", str(filename))[:130].strip() or "NUNES Catalogue.pdf"
    if not filename.casefold().endswith(".pdf"):
        filename += ".pdf"
    data = Path(path).read_bytes()
    if not data.startswith(b"%PDF-") or len(data) > 5_000_000:
        raise ValueError("Only generated PDF files under 5 MB may be saved.")
    try:
        client = _get_drive_client()
        target_folder = _destination_folder(client, kind)
        created = client.upload_pdf(filename, target_folder, data)
        file_id = created.get("id")
        if not file_id or not re.fullmatch(r"[A-Za-z0-9_-]+", file_id):
            raise DriveConfigurationError("Google Drive did not return a valid file ID.")
        return created.get("webViewLink") or "https://drive.google.com/file/d/" + file_id + "/view"
    except DriveConfigurationError:
        raise
    except Exception as exc:
        raise DriveConfigurationError(
            "Google Drive upload failed. Check service-account folder access, "
            "Drive API and Shared Drive storage quota."
        ) from exc


def archive_pdf_entries(contents):
    """Validate a generated ZIP and return bounded (name, kind, bytes) items."""
    import zipfile
    if not isinstance(contents, (bytes, bytearray)) or len(contents) > 28_000_000:
        raise ValueError("Catalogue archive missing or too large for Drive upload.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(contents), "r")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        raise ValueError("Invalid catalogue ZIP archive.") from exc
    output = []
    with archive:
        for item in archive.infolist():
            name = item.filename
            if item.is_dir() or not name.casefold().endswith(".pdf"):
                continue
            if len(output) >= 12 or item.file_size > 5_000_000:
                raise ValueError("Catalogue ZIP contains too many or oversized PDFs.")
            if name.startswith("Full_Catalogues/"):
                kind = "full"
            elif name.startswith("Mini_Catalogue/"):
                kind = "mini"
            elif "/" not in name:
                kind = "full"
            else:
                raise ValueError("Unexpected PDF folder inside catalogue ZIP.")
            filename = Path(name).name
            if (not filename or filename in (".", "..") or
                    not filename.casefold().endswith(".pdf")):
                raise ValueError("Catalogue archive contains an invalid PDF name.")
            pdf = archive.read(item)
            if not pdf.startswith(b"%PDF-") or len(pdf) > 5_000_000:
                raise ValueError("Archive entry is not a valid bounded PDF file.")
            output.append((filename, kind, pdf))
    if not output:
        raise ValueError("Catalogue ZIP contains no PDF files to save.")
    return output


def save_catalogue_archive(contents, token: str = "", allow_server_token: bool = False):
    """Save Full/Mini PDFs inside an already-generated ZIP in their Drive folders."""
    if not configured():
        raise DriveConfigurationError("Google Drive saving is not configured.")
    expected = _owner_save_token()
    if not authorized(token):
        if allow_server_token and len(expected) >= 16:
            pass
        else:
            raise PermissionError("Incorrect Drive save code.")
    entries = archive_pdf_entries(contents)
    try:
        client = _get_drive_client()
        destinations = {}
        for _, kind, _ in entries:
            if kind not in destinations:
                destinations[kind] = _destination_folder(client, kind)
        report = {"attempted": len(entries), "saved": 0, "full": 0, "mini": 0,
                  "failed": 0, "first_link": ""}
        for filename, kind, data in entries:
            safe_name = re.sub(r"[^a-zA-Z0-9 _().-]", "_", filename)[:130].strip() or "NUNES Catalogue.pdf"
            try:
                created = client.upload_pdf(safe_name, destinations[kind], data)
                identifier = str(created.get("id") or "")
                if not re.fullmatch(r"[A-Za-z0-9_-]{10,160}", identifier):
                    raise ValueError("Drive file ID was missing.")
                report["saved"] += 1
                report[kind] += 1
                if not report["first_link"]:
                    report["first_link"] = created.get("webViewLink") or f"https://drive.google.com/file/d/{identifier}/view"
            except Exception:
                report["failed"] += 1
        return report
    except DriveConfigurationError:
        raise
    except Exception as exc:
        raise DriveConfigurationError("Failed saving catalogue archive to Google Drive.") from exc
