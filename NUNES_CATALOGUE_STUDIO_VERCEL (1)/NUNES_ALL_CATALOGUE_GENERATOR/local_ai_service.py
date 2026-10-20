import base64
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


class LocalAIService:
    """Small, conservative Ollama wrapper for product drafting.

    The service never claims Ollama is connected unless a real request succeeds.
    It prefers a local Qwen-compatible text model and falls back to the first
    discovered model when necessary.
    """

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL, timeout: int = 120, max_retries: int = 1):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NUNES-Catalogue-Studio/1.0"})

    def _request_json(self, method: str, path: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(method, url, timeout=self.timeout, json=payload)
                if resp.status_code >= 500 and attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                if resp.status_code >= 400:
                    try:
                        body = resp.json()
                    except ValueError:
                        body = {"error": resp.text[:300]}
                    raise RuntimeError(body.get("error") or f"HTTP {resp.status_code}")
                try:
                    return resp.json()
                except ValueError as exc:
                    raise RuntimeError("Invalid JSON response from Ollama") from exc
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                raise
        raise RuntimeError(str(last_error) if last_error else "Ollama request failed")

    def discover_models(self) -> List[str]:
        try:
            data = self._request_json("GET", "/api/tags")
        except Exception:
            return []
        models = data.get("models") or []
        names: List[str] = []
        for item in models:
            name = item.get("name") or item.get("model") or ""
            if name:
                names.append(str(name))
        return names

    def preferred_model(
        self,
        preferred_prefixes: Optional[Iterable[str]] = None,
        models: Optional[Iterable[str]] = None,
    ) -> str:
        names = list(models) if models is not None else self.discover_models()
        if not names:
            return ""
        prefixes = tuple((preferred_prefixes or ["qwen", "llama", "mistral", "gemma", "deepseek", "phi"]))
        for prefix in prefixes:
            for name in names:
                if name.lower().startswith(prefix.lower()):
                    return name
        return names[0]

    def ping(self) -> bool:
        try:
            self._request_json("GET", "/api/tags")
            return True
        except Exception:
            return False

    def _extract_json_object(self, text: str) -> Dict[str, Any]:
        blob = text.strip()
        if not blob:
            raise ValueError("Ollama returned an empty response.")

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.DOTALL | re.IGNORECASE)
        if fenced:
            blob = fenced.group(1)
        else:
            start = blob.find("{")
            end = blob.rfind("}")
            if start != -1 and end > start:
                blob = blob[start:end + 1]

        try:
            data = json.loads(blob)
        except json.JSONDecodeError as exc:
            raise ValueError("Ollama did not return valid JSON for the catalogue draft.") from exc

        if not isinstance(data, dict):
            raise ValueError("The AI response was not a JSON object.")
        return data

    def _normalise_list(self, value: Any, limit: int = 8) -> List[str]:
        if value is None:
            return []

        def flatten(item: Any) -> List[str]:
            if isinstance(item, dict):
                out: List[str] = []
                for k, v in item.items():
                    if isinstance(v, (dict, list, tuple, set)):
                        out.extend(flatten(v))
                    else:
                        text = f"{k}: {v}".strip()
                        if text:
                            out.append(text)
                return out
            if isinstance(item, (list, tuple, set)):
                out = []
                for sub in item:
                    out.extend(flatten(sub))
                return out
            text = str(item).strip()
            return [text] if text else []

        cleaned: List[str] = []
        for item in flatten(value):
            if item and len(cleaned) < limit:
                cleaned.append(item)
        return cleaned

    def _build_prompt(self, product: str, model: str, datasheet_text: str, image_note: str = "") -> str:
        prompt = f"""
You are generating a product catalogue draft for a B2B industrial equipment supplier.

Rules:
- Use only the supplied product name, model, image hints, and datasheet text when available.
- Never invent exact ranges, resolution, voltage, dimensions, warranty, manufacturer, country of origin, certifications, or other unverified facts.
- For any specification that is unknown or unverified, write 'Verification Required' or omit it.
- Return valid JSON only.
- The output MUST be a JSON object with keys: product_name, model, description, key_features, applications, specifications, keywords, mini_caption, summary, verification_status, sources

Product name: {product}
Model: {model or ""}
Image notes: {image_note or "No image understanding available; infer only from product name and supplied context."}
Datasheet text: {datasheet_text[:4000] or "No datasheet text supplied."}
"""
        return prompt

    def _image_message(self, image_path_or_url: Optional[str]) -> Optional[str]:
        if not image_path_or_url:
            return None
        src = image_path_or_url.strip()
        if not src:
            return None
        if src.startswith("http://") or src.startswith("https://"):
            return src
        p = Path(src)
        if p.exists():
            try:
                with p.open("rb") as img:
                    encoded = base64.b64encode(img.read()).decode("ascii")
                    return encoded
            except OSError:
                return None
        return None

    def generate_product_draft(
        self,
        product: str,
        model: str = "",
        image: Optional[str] = None,
        datasheet_text: str = "",
        *,
        preferred_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        product = (product or "").strip()
        if not product:
            raise ValueError("A product name is required to generate the catalogue draft.")

        model_name = preferred_model or self.preferred_model()
        if not model_name:
            raise RuntimeError("No local Ollama model was detected. Install a compatible model such as qwen2.5 or qwen2.5vl and retry.")

        image_note = "A product image was supplied for visual context." if image else "No image was supplied."
        prompt = self._build_prompt(product, model, datasheet_text, image_note)

        payload: Dict[str, Any] = {
            "model": model_name,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.2, "num_predict": 1800},
            "messages": [{"role": "user", "content": prompt}],
        }

        image_payload = self._image_message(image)
        if image_payload and ("vision" in model_name.lower() or "vl" in model_name.lower() or "llava" in model_name.lower()):
            payload["messages"] = [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "source": {"type": "base64", "data": image_payload, "media_type": "image/jpeg"}},
                ],
            }]

        response = self._request_json("POST", "/api/chat", payload)
        raw = ""
        if isinstance(response, dict):
            raw = response.get("message", {}).get("content") or response.get("content") or ""
        if not raw and isinstance(response, str):
            raw = response
        if not raw:
            raise RuntimeError("Ollama returned no content for the generation request.")

        data = self._extract_json_object(str(raw))
        required = [
            "product_name",
            "model",
            "description",
            "key_features",
            "applications",
            "specifications",
            "keywords",
            "mini_caption",
            "summary",
            "verification_status",
            "sources",
        ]
        for field in required:
            if field not in data:
                data[field] = "" if field in {"description", "mini_caption", "summary", "product_name", "model"} else []

        data["product_name"] = str(data.get("product_name") or product).strip() or product
        data["model"] = str(data.get("model") or model).strip()
        data["description"] = str(data.get("description") or "").strip()
        data["mini_caption"] = str(data.get("mini_caption") or data.get("summary") or "").strip()
        data["summary"] = str(data.get("summary") or data.get("description") or "").strip()
        data["verification_status"] = "review_required"
        data["key_features"] = self._normalise_list(data.get("key_features"), limit=8)
        data["applications"] = self._normalise_list(data.get("applications"), limit=8)
        data["keywords"] = self._normalise_list(data.get("keywords"), limit=12)
        data["specifications"] = self._normalise_list(data.get("specifications"), limit=12)
        if not isinstance(data.get("sources"), list):
            data["sources"] = []
        data["sources"] = [str(x) for x in data.get("sources", []) if str(x).strip()][:10]

        if not data["description"]:
            data["description"] = f"{data['product_name']} is a product drafted from the local AI workflow. Verify all technical claims before publication."
        if not data["summary"]:
            data["summary"] = data["description"][:240]
        if not data["mini_caption"]:
            data["mini_caption"] = data["product_name"]

        return data


def build_local_ai_status() -> Dict[str, Any]:
    service = LocalAIService()
    try:
        data = service._request_json("GET", "/api/tags")
    except Exception:
        return {
            "available": False,
            "api_reachable": False,
            "models": [],
            "preferred_model": "",
            "message": "The local Ollama API could not be reached.",
        }
    models = [
        str(item.get("name") or item.get("model"))
        for item in data.get("models", [])
        if item.get("name") or item.get("model")
    ]
    preferred = service.preferred_model(models=models)
    return {
        "available": bool(models),
        "api_reachable": True,
        "models": models,
        "preferred_model": preferred,
        "message": (
            "Ollama is reachable, but no local models are installed."
            if not models
            else f"Ollama API is reachable with {len(models)} local model(s); inference is verified when generation succeeds."
        ),
    }
