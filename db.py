"""
NephroGuard & ShiftPass v3.0 — Resilient SQLite Persistence Layer with Automatic
Schema Migration & 5 Realistic Ward/ICU Clinical Cases.
"""

from __future__ import annotations
import json
import os
import sqlite3
import tempfile
import time
from uuid import uuid4
from typing import Any, Dict, List, Optional


SEED_PATIENTS: List[Dict[str, Any]] = [
    {
        "id": "case_1_sarcopenic_afib",
        "name": "Training case 01",
        "room": "Med-Surg 402A",
        "primary_diagnosis": "Non-Valvular Atrial Fibrillation, Osteoarthritis & Acute-on-Chronic Kidney Injury",
        "age": 83,
        "sex": "Female",
        "weight_kg": 52.0,
        "height_cm": 156.0,
        "scr_value": 1.6,
        "scr_unit": "mg_dl",
        "baseline_scr_mg_dl": 1.0,
        "delta_hours": 24.0,
        "cystatin_c_mg_l": 1.95,
        "potassium_meq_l": 5.3,
        "weight_override": "auto",
        "rrt_modality": "none",
        "crrt_effluent_ml_kg_h": 25.0,
        "medications": [
            {"drug_id": "apixaban", "current_dose": "5 mg PO BID"},
            {"drug_id": "lisinopril", "current_dose": "20 mg PO daily"},
            {"drug_id": "furosemide", "current_dose": "40 mg PO daily"},
            {"drug_id": "ibuprofen", "current_dose": "400 mg PO TID PRN"},
            {"drug_id": "gabapentin", "current_dose": "600 mg PO TID"},
        ],
    },
    {
        "id": "case_2_obese_sepsis",
        "name": "Training case 02",
        "room": "ICU Bed 07",
        "primary_diagnosis": "MRSA Bacteremia & Healthcare-Associated Pneumonia (Class III Obesity)",
        "age": 58,
        "sex": "Male",
        "weight_kg": 132.0,
        "height_cm": 178.0,
        "scr_value": 1.4,
        "scr_unit": "mg_dl",
        "baseline_scr_mg_dl": 1.3,
        "delta_hours": 24.0,
        "cystatin_c_mg_l": None,
        "potassium_meq_l": 4.4,
        "weight_override": "auto",
        "rrt_modality": "none",
        "crrt_effluent_ml_kg_h": 25.0,
        "medications": [
            {"drug_id": "vancomycin", "current_dose": "1500 mg IV q12h"},
            {"drug_id": "piperacillin_tazobactam", "current_dose": "4.5 g IV q6h"},
            {"drug_id": "metformin", "current_dose": "1000 mg PO BID"},
            {"drug_id": "enoxaparin", "current_dose": "40 mg SC daily"},
        ],
    },
    {
        "id": "case_3_ckd4_hyperk",
        "name": "Training case 03",
        "room": "Stepdown 214B",
        "primary_diagnosis": "CKD Stage G4, Type 2 Diabetes, Complicated UTI & Acute Gout Flare",
        "age": 71,
        "sex": "Male",
        "weight_kg": 76.0,
        "height_cm": 172.0,
        "scr_value": 2.6,
        "scr_unit": "mg_dl",
        "baseline_scr_mg_dl": 2.4,
        "delta_hours": 48.0,
        "cystatin_c_mg_l": 2.3,
        "potassium_meq_l": 5.6,
        "weight_override": "auto",
        "rrt_modality": "none",
        "crrt_effluent_ml_kg_h": 25.0,
        "medications": [
            {"drug_id": "metformin", "current_dose": "1000 mg PO BID"},
            {"drug_id": "spironolactone", "current_dose": "25 mg PO daily"},
            {"drug_id": "losartan", "current_dose": "50 mg PO daily"},
            {"drug_id": "tmp_smx", "current_dose": "1 DS tablet PO BID"},
            {"drug_id": "colchicine", "current_dose": "0.6 mg PO BID"},
            {"drug_id": "allopurinol", "current_dose": "300 mg PO daily"},
        ],
    },
    {
        "id": "case_4_postop_ortho",
        "name": "Training case 04",
        "room": "Ortho-Surg 309",
        "primary_diagnosis": "Post-Op Total Hip Arthroplasty, Acute Post-Op Pain & Rapid Pre-Renal AKI",
        "age": 68,
        "sex": "Female",
        "weight_kg": 64.0,
        "height_cm": 162.0,
        "scr_value": 1.9,
        "scr_unit": "mg_dl",
        "baseline_scr_mg_dl": 1.1,
        "delta_hours": 18.0,
        "cystatin_c_mg_l": None,
        "potassium_meq_l": 4.7,
        "weight_override": "auto",
        "rrt_modality": "none",
        "crrt_effluent_ml_kg_h": 25.0,
        "medications": [
            {"drug_id": "enoxaparin", "current_dose": "60 mg SC q12h"},
            {"drug_id": "rivaroxaban", "current_dose": "20 mg PO daily"},
            {"drug_id": "ketorolac", "current_dose": "30 mg IV q6h"},
            {"drug_id": "morphine", "current_dose": "8 mg IV q4h PRN"},
            {"drug_id": "cefepime", "current_dose": "2 g IV q8h"},
        ],
    },
    {
        "id": "case_5_icu_crrt_shock",
        "name": "Training case 05",
        "room": "MICU Bed 02",
        "primary_diagnosis": "Septic Shock, Candidemia & Anuric AKI on Continuous Renal Replacement Therapy (CVVHDF)",
        "age": 62,
        "sex": "Male",
        "weight_kg": 82.0,
        "height_cm": 174.0,
        "scr_value": 3.4,
        "scr_unit": "mg_dl",
        "baseline_scr_mg_dl": 1.1,
        "delta_hours": 24.0,
        "cystatin_c_mg_l": 2.8,
        "potassium_meq_l": 5.1,
        "weight_override": "auto",
        "rrt_modality": "crrt",
        "crrt_effluent_ml_kg_h": 30.0,
        "medications": [
            {"drug_id": "meropenem", "current_dose": "500 mg IV q24h"},
            {"drug_id": "vancomycin", "current_dose": "1000 mg IV q12h"},
            {"drug_id": "fluconazole", "current_dose": "200 mg IV q24h"},
            {"drug_id": "famotidine", "current_dose": "20 mg IV BID"},
        ],
    },
]


class NephroGuardDB:
    def __init__(self, db_path: Optional[str] = None) -> None:
        default_path = os.path.join(tempfile.gettempdir(), "nephroguard_v3.db")
        self.db_path = db_path or default_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        try:
            conn.execute("BEGIN IMMEDIATE")
            first_run = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'patients'"
            ).fetchone() is None
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS patients (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    room TEXT NOT NULL,
                    primary_diagnosis TEXT NOT NULL,
                    age REAL NOT NULL,
                    sex TEXT NOT NULL,
                    weight_kg REAL NOT NULL,
                    height_cm REAL NOT NULL,
                    scr_value REAL NOT NULL,
                    scr_unit TEXT NOT NULL,
                    baseline_scr_mg_dl REAL,
                    delta_hours REAL NOT NULL DEFAULT 24.0,
                    cystatin_c_mg_l REAL,
                    potassium_meq_l REAL NOT NULL,
                    weight_override TEXT NOT NULL DEFAULT 'auto',
                    rrt_modality TEXT NOT NULL DEFAULT 'none',
                    crrt_effluent_ml_kg_h REAL NOT NULL DEFAULT 25.0,
                    medications_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            # Safe schema migration for older v2.4 tables if present
            existing_cols = {
                row["name"] for row in conn.execute("PRAGMA table_info(patients)").fetchall()
            }
            migrations = [
                ("delta_hours", "ALTER TABLE patients ADD COLUMN delta_hours REAL NOT NULL DEFAULT 24.0"),
                ("cystatin_c_mg_l", "ALTER TABLE patients ADD COLUMN cystatin_c_mg_l REAL"),
                ("rrt_modality", "ALTER TABLE patients ADD COLUMN rrt_modality TEXT NOT NULL DEFAULT 'none'"),
                ("crrt_effluent_ml_kg_h", "ALTER TABLE patients ADD COLUMN crrt_effluent_ml_kg_h REAL NOT NULL DEFAULT 25.0"),
            ]
            for col_name, ddl in migrations:
                if col_name not in existing_cols:
                    conn.execute(ddl)

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS handoff_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id TEXT NOT NULL,
                    patient_name TEXT NOT NULL,
                    illness_severity TEXT NOT NULL,
                    safety_score INTEGER NOT NULL,
                    handoff_markdown TEXT NOT NULL,
                    signed_by TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            if first_run:
                for p in SEED_PATIENTS:
                    self.upsert_patient(p, conn=conn)
            conn.commit()
        finally:
            conn.close()

    def upsert_patient(
        self, payload: Dict[str, Any], conn: Optional[sqlite3.Connection] = None
    ) -> Dict[str, Any]:
        own_conn = False
        if conn is None:
            conn = self._get_conn()
            own_conn = True
        try:
            pid = str(payload.get("id") or f"pt_{uuid4().hex}")
            meds = payload.get("medications", [])
            now = time.time()
            conn.execute(
                """
                INSERT INTO patients (
                    id, name, room, primary_diagnosis, age, sex, weight_kg, height_cm,
                    scr_value, scr_unit, baseline_scr_mg_dl, delta_hours, cystatin_c_mg_l,
                    potassium_meq_l, weight_override, rrt_modality, crrt_effluent_ml_kg_h,
                    medications_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    room=excluded.room,
                    primary_diagnosis=excluded.primary_diagnosis,
                    age=excluded.age,
                    sex=excluded.sex,
                    weight_kg=excluded.weight_kg,
                    height_cm=excluded.height_cm,
                    scr_value=excluded.scr_value,
                    scr_unit=excluded.scr_unit,
                    baseline_scr_mg_dl=excluded.baseline_scr_mg_dl,
                    delta_hours=excluded.delta_hours,
                    cystatin_c_mg_l=excluded.cystatin_c_mg_l,
                    potassium_meq_l=excluded.potassium_meq_l,
                    weight_override=excluded.weight_override,
                    rrt_modality=excluded.rrt_modality,
                    crrt_effluent_ml_kg_h=excluded.crrt_effluent_ml_kg_h,
                    medications_json=excluded.medications_json,
                    updated_at=excluded.updated_at
                """,
                (
                    pid,
                    str(payload.get("name", "Unnamed Patient")),
                    str(payload.get("room", "Ward Bed")),
                    str(payload.get("primary_diagnosis", "Inpatient Care")),
                    float(payload["age"]),
                    str(payload["sex"]),
                    float(payload["weight_kg"]),
                    float(payload["height_cm"]),
                    float(payload["scr_value"]),
                    str(payload.get("scr_unit", "mg_dl")),
                    (
                        float(payload["baseline_scr_mg_dl"])
                        if payload.get("baseline_scr_mg_dl") not in (None, "")
                        else None
                    ),
                    float(payload.get("delta_hours", 24.0) or 24.0),
                    (
                        float(payload["cystatin_c_mg_l"])
                        if payload.get("cystatin_c_mg_l") not in (None, "")
                        else None
                    ),
                    float(payload.get("potassium_meq_l", 4.2)),
                    str(payload.get("weight_override", "auto")),
                    str(payload.get("rrt_modality", "none") or "none"),
                    float(payload.get("crrt_effluent_ml_kg_h", 25.0) or 25.0),
                    json.dumps(meds),
                    now,
                ),
            )
            if own_conn:
                conn.commit()
            return self.get_patient(pid, conn=conn)  # type: ignore
        finally:
            if own_conn:
                conn.close()

    def get_patient(
        self, patient_id: str, conn: Optional[sqlite3.Connection] = None
    ) -> Optional[Dict[str, Any]]:
        own_conn = False
        if conn is None:
            conn = self._get_conn()
            own_conn = True
        try:
            row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
            if not row:
                return None
            return self._row_to_dict(row)
        finally:
            if own_conn:
                conn.close()

    def list_patients(self) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM patients ORDER BY id ASC").fetchall()
            return [self._row_to_dict(r) for r in rows]
        finally:
            conn.close()

    def delete_patient(self, patient_id: str) -> bool:
        conn = self._get_conn()
        try:
            cur = conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()

    def log_handoff(
        self,
        patient_id: str,
        patient_name: str,
        illness_severity: str,
        safety_score: int,
        handoff_markdown: str,
        signed_by: str = "On-Call Pharmacist / Resident",
    ) -> Dict[str, Any]:
        now = time.time()
        conn = self._get_conn()
        try:
            cur = conn.execute(
                """
                INSERT INTO handoff_logs (
                    patient_id, patient_name, illness_severity, safety_score,
                    handoff_markdown, signed_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    patient_name,
                    illness_severity,
                    int(safety_score),
                    handoff_markdown,
                    signed_by,
                    now,
                ),
            )
            conn.commit()
            return {
                "log_id": cur.lastrowid,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "illness_severity": illness_severity,
                "safety_score": safety_score,
                "signed_by": signed_by,
                "created_at": now,
            }
        finally:
            conn.close()

    def list_handoff_logs(self, limit: int = 25) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT * FROM handoff_logs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = dict(row)
        d["medications"] = json.loads(d.pop("medications_json", "[]"))
        return d
