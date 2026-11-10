"""
NephroGuard & ShiftPass v3.0 — Full-Stack HTTP API Server & Static Application Host.
Supports HL7 FHIR R4 Bundle Export (/api/fhir/<patient_id>), Multilingual Patient Handouts,
Kinetic eGFR, 2021 CKD-EPI Creatinine-Cystatin C, and RRT/CRRT Dosing.
"""

from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

from db import NephroGuardDB
from engine import FORMULARY, evaluate_full_patient_case
from validation import validate_case

ROOT = Path(__file__).resolve().parent
DEFAULT_UI = ROOT / "nephroguard_app.html"
ASSETS = {"/assets/app.js": ("app.js", "text/javascript"),
          "/assets/app.css": ("app.css", "text/css")}
MAX_BODY_BYTES = 256 * 1024


class NephroGuardHandler(BaseHTTPRequestHandler):
    timeout = 10
    db: NephroGuardDB = None  # type: ignore
    ui_html_path = DEFAULT_UI

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{kind}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: object) -> None:
        self._send(status, json.dumps(payload, allow_nan=False).encode("utf-8"), "application/json")

    def _request_allowed(self) -> bool:
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if self.server.server_address[0] == "127.0.0.1":
            allowed = {"localhost", "127.0.0.1"}
            allowed |= {f"{name}:{self.server.server_port}" for name in tuple(allowed)}
            if host and host.lower() not in allowed:
                self._send_json(403, {"error": "Open the application using its loopback address."})
                return False
        if origin and origin != f"http://{host}":
            self._send_json(403, {"error": "Cross-origin requests are disabled."})
            return False
        return True

    def _case_result(self, patient: dict) -> dict:
        try:
            return {"patient_record": patient, "evaluation": evaluate_full_patient_case(validate_case(patient))}
        except (KeyError, ValueError, TypeError, ArithmeticError):
            return {"patient_record": patient, "evaluation": None, "error": "This saved case has invalid inputs. Review and save the inputs again."}

    def do_OPTIONS(self) -> None:
        if self._request_allowed():
            self._send_json(200, {"status": "ok"})

    def do_GET(self) -> None:
        if not self._request_allowed():
            return
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            try:
                self._send(200, Path(self.ui_html_path).read_bytes(), "text/html")
            except FileNotFoundError:
                self._send_json(404, {"error": "The browser application file is missing."})
            return

        if path in ASSETS:
            filename, kind = ASSETS[path]
            self._send(200, (ROOT / "assets" / filename).read_bytes(), kind)
            return

        if path == "/api/health":
            self._send_json(
                200,
                {
                    "status": "healthy",
                    "version": "3.0.0",
                    "service": "NephroGuard & ShiftPass Clinical Engine",
                    "formulary_count": len(FORMULARY),
                    "patients_count": len(self.db.list_patients()),
                },
            )
            return

        if path == "/api/formulary":
            self._send_json(200, {"formulary": list(FORMULARY.values())})
            return

        if path == "/api/patients":
            patients = self.db.list_patients()
            evaluated = [self._case_result(p) for p in patients]
            self._send_json(200, {"patients": evaluated})
            return

        if path.startswith("/api/patients/"):
            pid = unquote(path.removeprefix("/api/patients/").strip("/"))
            p = self.db.get_patient(pid)
            if not p:
                self._send_json(404, {"error": f"Patient '{pid}' not found"})
                return
            self._send_json(200, self._case_result(p))
            return

        if path.startswith("/api/fhir/"):
            pid = unquote(path.removeprefix("/api/fhir/").strip("/"))
            p = self.db.get_patient(pid)
            if not p:
                self._send_json(404, {"error": f"Patient '{pid}' not found"})
                return
            result = self._case_result(p)
            ev = result["evaluation"]
            if ev is None:
                self._send_json(422, {"error": result["error"]})
                return
            self._send_json(200, ev["fhir_bundle"])
            return

        if path == "/api/handoffs":
            self._send_json(200, {"handoff_logs": self.db.list_handoff_logs()})
            return

        self._send_json(404, {"error": f"Unknown endpoint: {path}"})

    def do_POST(self) -> None:
        if not self._request_allowed():
            return
        path = urlparse(self.path).path
        if path not in {"/api/evaluate", "/api/patients", "/api/handoffs"}:
            self._send_json(404, {"error": "Unknown endpoint."})
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "Send an application/json request."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError
        except ValueError:
            self._send_json(400, {"error": "A positive Content-Length is required."})
            return
        if length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "Case payload exceeds 256 KiB."})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, RecursionError):
            self._send_json(400, {"error": "Malformed UTF-8 JSON payload."})
            return

        try:
            payload = validate_case(payload)
            if path == "/api/evaluate":
                result = evaluate_full_patient_case(payload)
                self._send_json(200, result)
                return

            if path == "/api/patients":
                payload["id"] = payload.get("id") or f"pt_{uuid4().hex}"
                eval_res = evaluate_full_patient_case(payload)
                json.dumps(eval_res, allow_nan=False)
                saved = self.db.upsert_patient(payload)
                self._send_json(201, {"patient_record": saved, "evaluation": eval_res})
                return

            if path == "/api/handoffs":
                eval_res = evaluate_full_patient_case(payload)
                log_entry = self.db.log_handoff(
                    patient_id=str(payload.get("id", "custom")),
                    patient_name=str(payload.get("name", "Patient")),
                    illness_severity=eval_res["ipass"]["illness_severity"],
                    safety_score=eval_res["safety_score"],
                    handoff_markdown=eval_res["ipass"]["markdown"],
                    signed_by=str(payload.get("signed_by", "Clinical Pharmacist")),
                )
                self._send_json(201, {"handoff_log": log_entry, "ipass": eval_res["ipass"]})
                return

        except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
            self._send_json(422, {"error": str(exc)})
        except sqlite3.Error:
            self._send_json(503, {"error": "Could not write to the case database."})

    def do_DELETE(self) -> None:
        if not self._request_allowed():
            return
        path = urlparse(self.path).path
        if path.startswith("/api/patients/"):
            pid = unquote(path.removeprefix("/api/patients/").strip("/"))
            deleted = self.db.delete_patient(pid)
            if not deleted:
                self._send_json(404, {"error": f"Patient '{pid}' not found"})
                return
            self._send_json(200, {"deleted": pid})
            return
        self._send_json(404, {"error": f"Unknown DELETE endpoint: {path}"})

    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write(f"[NephroGuard v3.0 HTTP] {self.address_string()} - {fmt % args}\n")


def run_server(host: str = "127.0.0.1", port: int = 8765, db_path: str | None = None, ui_html: str | Path = DEFAULT_UI) -> None:
    NephroGuardHandler.db = NephroGuardDB(db_path=db_path)
    NephroGuardHandler.ui_html_path = ui_html
    server = HTTPServer((host, port), NephroGuardHandler)
    print(f"NephroGuard & ShiftPass v3.0 server listening on http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NephroGuard & ShiftPass v3.0 Full-Stack Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--db", default=None)
    parser.add_argument("--ui", default=DEFAULT_UI)
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, db_path=args.db, ui_html=args.ui)
