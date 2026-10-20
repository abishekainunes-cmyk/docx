"""
Image Processing & Background Removal Engine for NUNES Catalogue Studio.
Supports:
1. Studio background removal using edge-connected alpha flood-fill for light/white backgrounds.
2. Optional rembg u2netp integration if installed in the environment.
3. Aspect ratio preservation, resizing, and transparent PNG output.
4. Image downloading, verification, and candidate handling.
"""
from __future__ import annotations

import io
import os
import re
import tempfile
from collections import deque
from pathlib import Path
from typing import Optional, Tuple
import requests
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10_000_000
MAX_SIDE = 1400


class BackgroundRemovalError(ValueError):
    pass


def remove_studio_background(image_bytes: bytes) -> bytes:
    """Removes clean white/light studio background and returns transparent PNG bytes."""
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise BackgroundRemovalError(f"Image too large ({len(image_bytes)} bytes). Max allowed is 10 MB.")

    try:
        picture = Image.open(io.BytesIO(image_bytes))
    except (UnidentifiedImageError, OSError) as exc:
        raise BackgroundRemovalError(f"Cannot identify image format: {exc}")

    # Resize if excessively large to save memory
    w, h = picture.size
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
        picture = picture.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
        w, h = picture.size

    # Try rembg if available
    try:
        from rembg import remove, new_session
        session = new_session("u2netp")
        buf = io.BytesIO()
        picture.save(buf, format="PNG")
        res = remove(buf.getvalue(), session=session)
        if res and len(res) > 500:
            return res
    except Exception:
        pass

    # High-quality fallback: flood fill from borders for studio white/light backgrounds
    rgba = picture.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A").getextrema()
    if alpha and alpha[0] < 250:
        # Already has transparency
        out = io.BytesIO()
        rgba.save(out, format="PNG", optimize=True)
        return out.getvalue()

    rgb = rgba.convert("RGB").tobytes()

    def is_bg(idx: int) -> bool:
        at = idx * 3
        r, g, b = rgb[at], rgb[at + 1], rgb[at + 2]
        return min(r, g, b) >= 210 and (max(r, g, b) - min(r, g, b)) <= 42

    sample = []
    step_x = max(1, w // 50)
    step_y = max(1, h // 50)
    for x in range(0, w, step_x):
        sample.extend((x, (h - 1) * w + x))
    for y in range(0, h, step_y):
        sample.extend((y * w, y * w + w - 1))

    if not sample or sum(is_bg(i) for i in sample) / len(sample) < 0.65:
        # Not a plain background, return clean PNG without destroying product
        out = io.BytesIO()
        rgba.save(out, format="PNG", optimize=True)
        return out.getvalue()

    mask = bytearray(b"\xff") * (w * h)
    q = deque()

    for idx in sample:
        if mask[idx] and is_bg(idx):
            mask[idx] = 0
            q.append(idx)

    while q:
        idx = q.popleft()
        x = idx % w
        if x > 0 and mask[idx - 1] and is_bg(idx - 1):
            mask[idx - 1] = 0
            q.append(idx - 1)
        if x + 1 < w and mask[idx + 1] and is_bg(idx + 1):
            mask[idx + 1] = 0
            q.append(idx + 1)
        if idx >= w and mask[idx - w] and is_bg(idx - w):
            mask[idx - w] = 0
            q.append(idx - w)
        if idx + w < w * h and mask[idx + w] and is_bg(idx + w):
            mask[idx + w] = 0
            q.append(idx + w)

    rgba.putalpha(Image.frombytes("L", (w, h), bytes(mask)))
    out = io.BytesIO()
    rgba.save(out, format="PNG", optimize=True)
    return out.getvalue()


def download_product_image(url: str, timeout: int = 10) -> Optional[bytes]:
    """Downloads an image from a URL safely."""
    if not url or not url.startswith("http"):
        return None
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        if resp.status_code == 200 and "image" in resp.headers.get("Content-Type", "").lower() or len(resp.content) > 1000:
            return resp.content
    except Exception:
        pass
    return None
