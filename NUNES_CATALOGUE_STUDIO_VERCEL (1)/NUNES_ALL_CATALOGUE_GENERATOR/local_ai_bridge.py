"""
NUNES Local AI Bridge for Windows.
Bridges local Ollama running on your Windows PC to the hosted Vercel Catalogue Studio.

Features:
- Runs locally on your machine.
- Communicates with Ollama at http://127.0.0.1:11434.
- Exposes authenticated endpoints (/health, /generate).
- Protects requests with NUNES_BRIDGE_SECRET.
- Supports optional automated Cloudflare Tunnel (cloudflared quick tunnel)
  so Vercel can reach this bridge securely over HTTPS without port forwarding.
- Automatically notifies and registers with the Vercel web application.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from local_ai_service import LocalAIService

DEFAULT_BRIDGE_PORT = int(os.environ.get("NUNES_BRIDGE_PORT", "11435"))
DEFAULT_SECRET = os.environ.get("NUNES_BRIDGE_SECRET", "nunes_local_bridge_secret_2026")
DEFAULT_OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


class BridgeHandler(BaseHTTPRequestHandler):
    bridge_secret = DEFAULT_SECRET
    local_service = LocalAIService(base_url=DEFAULT_OLLAMA_URL)

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Secret, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Secret, Authorization")
        self.end_headers()

    def _is_authorized(self) -> bool:
        supplied = self.headers.get("X-Bridge-Secret", "")
        if not supplied:
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                supplied = auth_header[7:]
        if not supplied:
            query = parse_qs(urlparse(self.path).query)
            supplied = query.get("token", [""])[0]
        return hmac.compare_digest(supplied, self.bridge_secret)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            models = self.local_service.discover_models()
            is_alive = bool(models)
            preferred = self.local_service.preferred_model(models=models) if is_alive else ""
            self._send_json(200, {
                "status": "ok" if is_alive else "degraded",
                "service": "NUNES Local AI Windows Bridge",
                "ollama_connected": is_alive,
                "models": models,
                "preferred": preferred,
                "timestamp": time.time()
            })
            return

        self._send_json(404, {"error": "Not Found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if not self._is_authorized():
            self._send_json(401, {"error": "Unauthorized. Invalid or missing X-Bridge-Secret header."})
            return

        if parsed.path == "/generate":
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                self._send_json(400, {"error": "Empty payload"})
                return

            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception as e:
                self._send_json(400, {"error": f"Invalid JSON payload: {e}"})
                return

            product = payload.get("product", "").strip()
            model = payload.get("model", "").strip()
            datasheet = payload.get("datasheet_text", "") or payload.get("specifications", "")
            image_hints = payload.get("image_hints", "") or payload.get("image", "")

            if not product:
                self._send_json(400, {"error": "Product name is required"})
                return

            try:
                models = self.local_service.discover_models()
                if not models:
                    self._send_json(503, {"error": "Ollama is not running locally. Please start Ollama on your PC."})
                    return

                draft = self.local_service.generate_product_draft(
                    product=product,
                    model=model,
                    datasheet_text=datasheet,
                    image=image_hints
                )
                self._send_json(200, draft)
            except Exception as exc:
                self._send_json(500, {"error": f"Generation failed: {str(exc)}"})
            return

        self._send_json(404, {"error": "Not Found"})

    def log_message(self, format, *args):
        # Clean logging
        print(f"[{time.strftime('%H:%M:%S')}] {args[0]} - {args[1]}", flush=True)


def run_bridge(port: int = DEFAULT_BRIDGE_PORT, secret: str = DEFAULT_SECRET, vercel_url: str = ""):
    BridgeHandler.bridge_secret = secret
    server = HTTPServer(("127.0.0.1", port), BridgeHandler)
    
    print("=" * 65)
    print("  NUNES CATALOGUE GENERATOR — LOCAL AI WINDOWS BRIDGE")
    print("=" * 65)
    print(f" Local Bridge Port : {port}")
    print(f" Ollama Address    : {DEFAULT_OLLAMA_URL}")
    print(f" Secret Key        : {secret}")
    print("-" * 65)
    
    service = LocalAIService(base_url=DEFAULT_OLLAMA_URL)
    models = service.discover_models()
    if models:
        print(f" [OK] Ollama is active with models: {', '.join(models)}")
        print(f"      Default selected model: {service.preferred_model(models=models)}")
    else:
        print(" [WARNING] Ollama is not detected at 127.0.0.1:11434.")
        print("           Make sure Ollama is launched (e.g. 'ollama serve' or system tray).")
    
    print("-" * 65)
    print(f" Local endpoint: http://127.0.0.1:{port}/health")
    print(" To connect to hosted Vercel:")
    print(" 1. Run a tunnel (e.g. cloudflared tunnel --url http://localhost:11435)")
    print(" 2. Set NUNES_LOCAL_BRIDGE_URL in Vercel to your tunnel URL")
    print(" 3. Set NUNES_BRIDGE_SECRET in Vercel to match this secret")
    print("=" * 65)
    print(" Press Ctrl+C to stop the bridge.\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Local AI Bridge...")
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NUNES Local AI Bridge for Windows")
    parser.add_argument("--port", type=int, default=DEFAULT_BRIDGE_PORT, help="Bridge server port")
    parser.add_argument("--secret", type=str, default=DEFAULT_SECRET, help="Shared bridge secret")
    parser.add_argument("--vercel-url", type=str, default="", help="Vercel production URL for auto-register")
    args = parser.parse_args()

    run_bridge(port=args.port, secret=args.secret, vercel_url=args.vercel_url)
