import copy
import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path

from db import NephroGuardDB, SEED_PATIENTS
from server import NephroGuardHandler


class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        self.db = NephroGuardDB(str(self.path))
        handler = type("TestHandler", (NephroGuardHandler,), {
            "db": self.db,
            "log_message": lambda *args: None,
        })
        self.server = HTTPServer(("127.0.0.1", 0), handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None):
        client = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            client.request(method, path, data, headers or {})
            response = client.getresponse()
            return response.status, response.getheader("Content-Type"), response.read()
        finally:
            client.close()

    def post(self, path, payload, **headers):
        return self.request("POST", path, json.dumps(payload), {"Content-Type": "application/json", **headers})

    def test_default_ui_and_assets(self):
        status, kind, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", kind)
        self.assertIn(b"NephroGuard", body)
        self.assertEqual(self.request("GET", "/assets/app.js")[0], 200)
        self.assertEqual(self.request("GET", "/assets/../db.py")[0], 404)

    def test_evaluates_all_five_cases(self):
        status, _, body = self.request("GET", "/api/patients")
        self.assertEqual(status, 200)
        cases = json.loads(body)["patients"]
        self.assertEqual(len(cases), 5)
        for case in cases:
            self.assertIn("kinetics", case["evaluation"])
            self.assertEqual(len(case["evaluation"]["drug_evaluations"]), len(case["patient_record"]["medications"]))

    def test_invalid_payloads_fail_without_saving(self):
        for patch in ({"age": float("nan")}, {"sex": "unknown"}, {"medications": [{}]},
                      {"medications": [{"drug_id": "unknown"}]}, {"medications": ["bad"]}):
            status, _, _ = self.post("/api/patients", {**SEED_PATIENTS[0], **patch})
            self.assertIn(status, (400, 422))
        self.assertEqual(self.db.get_patient(SEED_PATIENTS[0]["id"])["sex"], SEED_PATIENTS[0]["sex"])
        self.assertEqual(self.post("/api/evaluate", [])[0], 422)
        self.assertEqual(self.request("POST", "/api/evaluate", b"\xff", {"Content-Type": "application/json"})[0], 400)

    def test_created_case_export_identity_and_encoded_lookup(self):
        case = copy.deepcopy(SEED_PATIENTS[0])
        case.pop("id")
        status, _, body = self.post("/api/patients", case)
        self.assertEqual(status, 201)
        saved = json.loads(body)
        self.assertEqual(saved["patient_record"]["id"], saved["evaluation"]["patient"]["id"])
        pid = saved["patient_record"]["id"]
        self.assertEqual(self.request("GET", "/api/fhir/" + pid)[0], 200)
        self.assertEqual(self.post("/api/patients", {**case, "id": "test case"})[0], 201)
        self.assertEqual(self.request("GET", "/api/patients/test%20case")[0], 200)
        self.assertEqual(self.request("DELETE", "/api/patients/test%20case")[0], 200)

    def test_local_writes_and_bad_lengths(self):
        self.assertEqual(self.post("/api/evaluate", SEED_PATIENTS[0], Origin="https://example.invalid")[0], 403)
        self.assertEqual(self.request("POST", "/api/evaluate", "{}", {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/evaluate", "", {"Content-Type": "application/json", "Content-Length": "-1"})[0], 400)

    def test_deleted_fixtures_stay_deleted_after_restart(self):
        for patient in self.db.list_patients():
            self.db.delete_patient(patient["id"])
        self.assertEqual(NephroGuardDB(str(self.path)).list_patients(), [])

    def test_explicit_invalid_database_does_not_fall_back(self):
        import sqlite3
        with self.assertRaises(sqlite3.OperationalError):
            NephroGuardDB(str(Path(self.tmp.name) / "missing" / "test.db"))

    def test_handoff_round_trip(self):
        case = {**SEED_PATIENTS[0], "signed_by": "Demo reviewer"}
        self.assertEqual(self.post("/api/handoffs", case)[0], 201)
        status, _, body = self.request("GET", "/api/handoffs")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["handoff_logs"][0]["signed_by"], "Demo reviewer")

    def test_invalid_legacy_case_does_not_hide_other_cases(self):
        self.db.upsert_patient({**SEED_PATIENTS[0], "id": "legacy", "medications": [{"drug_id": "unknown"}]})
        status, _, body = self.request("GET", "/api/patients")
        self.assertEqual(status, 200)
        cases = {item["patient_record"]["id"]: item for item in json.loads(body)["patients"]}
        self.assertIsNone(cases["legacy"]["evaluation"])
        self.assertIn("invalid inputs", cases["legacy"]["error"])
        self.assertIsNotNone(cases[SEED_PATIENTS[0]["id"]]["evaluation"])
