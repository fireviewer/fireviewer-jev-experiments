"""Local lab UI: actual progress events, private receipts and PNG captures.

Bind only to loopback; use AWS SSM port forwarding for the cloud lab.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import shadow
import components
import component_runner

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("FV_JEV_DATA_DIR", str(ROOT.parent / ".local" / "typesafe-lab")))
LOCK = threading.RLock()
STATE = {"run_id": None, "running": False, "events": [], "result": None, "cases": []}


def emit(event):
    with LOCK:
        item = {**event, "sequence": len(STATE["events"]),
                "at": datetime.now(timezone.utc).isoformat()}
        STATE["events"].append(item)
        if STATE["run_id"]:
            with (DATA / STATE["run_id"] / "events.jsonl").open("a") as stream:
                stream.write(json.dumps(item, ensure_ascii=False, allow_nan=False)+"\n")


def start_run(cases, execute, component_id):
    with LOCK:
        if STATE["running"]:
            raise ValueError("Une expérience est déjà en cours.")
        # Validate before starting a background job or creating a receipt.
        component_runner.run(cases, component_id=component_id)
        if execute and not os.environ.get("TYPESAFE_API_KEY"):
            raise ValueError("Accès TypeSafe absent côté serveur. Aucun appel envoyé.")
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:8]
        folder = DATA / run_id
        folder.mkdir(parents=True, mode=0o700)
        (folder / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2)+"\n")
        STATE.update(run_id=run_id, running=True, events=[], result=None, cases=cases,
                     component_id=component_id, mode="live" if execute else "offline_plan")

    def worker():
        try:
            emit({"type": "run_started", "total": len(cases), "mode": STATE["mode"]})
            result = component_runner.run(cases, component_id=component_id, execute=execute,
                                          api_key=os.environ.get("TYPESAFE_API_KEY"), on_event=emit)
            (folder / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
            with LOCK: STATE["result"] = result
            emit({"type": "run_finished", "report": result["report"]})
        except Exception as exc:
            emit({"type": "run_failed", "error_type": type(exc).__name__})
        finally:
            with LOCK: STATE["running"] = False

    threading.Thread(target=worker, daemon=True).start()
    return run_id


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "dashboard" / "dist"), **kwargs)

    def log_message(self, *args):
        pass  # no URLs or user evidence in console logs

    def json_reply(self, value, status=200):
        content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def local_request(self):
        host = self.headers.get("Host", "").split(":")[0]
        origin = self.headers.get("Origin")
        return host in {"localhost", "127.0.0.1"} and (not origin or urlparse(origin).netloc == self.headers.get("Host"))

    def do_GET(self):
        if not self.local_request():
            return self.json_reply({"error": "Accès via localhost / tunnel SSM uniquement."}, 403)
        route = urlparse(self.path).path
        if route == "/api/state":
            with LOCK:
                return self.json_reply({**STATE, "typesafe_ready": bool(os.environ.get("TYPESAFE_API_KEY")),
                                        "baseline_mode": "imported_component_receipts", "model": shadow.MODEL,
                                        "components": components.catalog()})
        if route == "/api/components":
            return self.json_reply(components.catalog())
        if route == "/api/export":
            with LOCK: return self.json_reply(STATE)
        if route == "/api/runs":
            runs = []
            for folder in sorted(DATA.glob("*"), reverse=True):
                if folder.is_dir():
                    runs.append({"id": folder.name, "complete": (folder/"result.json").exists(),
                                 "captures": len(list(folder.glob("capture-*.png")))})
            return self.json_reply(runs)
        if route == "/api/captures":
            return self.json_reply([{"run_id": path.parent.name, "name": path.name,
                "url": "/api/captures/"+path.parent.name+"/"+path.name}
                for path in sorted(DATA.glob("*/capture-*.png"), reverse=True)])
        capture_match = re.fullmatch(r"/api/captures/([0-9TZabcdef-]+)/capture-([0-9]+)\.png", route)
        if capture_match:
            path = DATA / capture_match[1] / ("capture-"+capture_match[2]+".png")
            if not path.is_file(): return self.json_reply({"error": "Capture introuvable"}, 404)
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if route.startswith("/api/run/"):
            run_id = route.rsplit("/", 1)[-1]
            if not run_id or any(c not in "0123456789TZ-abcdef" for c in run_id):
                return self.json_reply({"error": "Essai invalide"}, 400)
            folder = DATA / run_id
            if not (folder / "cases.json").exists():
                return self.json_reply({"error": "Essai introuvable"}, 404)
            return self.json_reply({"run_id": run_id, "running": False, "mode": "replay",
                "cases": json.loads((folder / "cases.json").read_text()),
                "events": [json.loads(x) for x in (folder / "events.jsonl").read_text().splitlines()],
                "result": json.loads((folder / "result.json").read_text()) if (folder / "result.json").exists() else None})
        if route.startswith("/api/"):
            return self.json_reply({"error": "Route inconnue"}, 404)
        return super().do_GET()

    def do_POST(self):
        if not self.local_request() or self.headers.get("Content-Type") != "application/json":
            return self.json_reply({"error": "Requête locale JSON requise"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 5_000_000:
                return self.json_reply({"error": "Requête trop volumineuse"}, 413)
            payload = json.loads(self.rfile.read(size))
            route = urlparse(self.path).path
            if route == "/api/credentials":
                key = payload.get("api_key")
                if not isinstance(key, str) or len(key) > 4096 or any(c.isspace() for c in key):
                    raise ValueError("Clé invalide")
                if key:
                    os.environ["TYPESAFE_API_KEY"] = key
                else:
                    os.environ.pop("TYPESAFE_API_KEY", None)
                return self.json_reply({"key_present": bool(key), "persisted": False})
            if route == "/api/run":
                mode = payload.get("mode")
                if mode not in {"offline_plan", "live"}: raise ValueError("Mode invalide")
                return self.json_reply({"run_id": start_run(payload["cases"], mode == "live", payload.get("component_id"))}, 202)
            if route == "/api/capture":
                with LOCK:
                    if not STATE["run_id"] or payload.get("run_id") != STATE["run_id"]:
                        raise ValueError("Lancer un essai avant de capturer sa progression")
                    png = base64.b64decode(payload["png"], validate=True)
                    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ValueError("Capture PNG requise")
                    path = DATA / STATE["run_id"] / ("capture-"+str(time.time_ns())+".png")
                    path.write_bytes(png)
                return self.json_reply({"saved": path.name})
            return self.json_reply({"error": "Route inconnue"}, 404)
        except (ValueError, TypeError, KeyError) as exc:
            return self.json_reply({"error": str(exc)[:160]}, 400)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    os.umask(0o077)
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    print(f"FireViewer laboratoire : http://127.0.0.1:{args.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
