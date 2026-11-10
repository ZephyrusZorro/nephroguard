#!/usr/bin/env python3
"""
NephroGuard & ShiftPass v3.0 — Command-Line Interface for Clinical Ward Audits,
I-PASS Exports, Multilingual Patient Handouts, and HL7 FHIR R4 Bundles.
"""

from __future__ import annotations
import argparse
import json
import sys
from db import NephroGuardDB
from engine import FORMULARY, evaluate_full_patient_case


def main() -> int:
    parser = argparse.ArgumentParser(
        description="NephroGuard & ShiftPass v3.0 CLI — Renal Pharmacokinetics, keGFR, RRT & I-PASS Engine"
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("list-ward", help="List all inpatient ward/ICU cases and their renal safety scores")

    audit_p = sub.add_parser("audit", help="Run full renal pharmacokinetic & syndrome audit on a patient ID")
    audit_p.add_argument("patient_id", help="Patient ID (e.g. case_1_sarcopenic_afib or case_5_icu_crrt_shock)")
    audit_p.add_argument("--format", choices=["text", "json", "ipass", "fhir", "handout-en", "handout-hi", "handout-kn"], default="text")

    sub.add_parser("formulary", help="List the bundled formulary medications and renal/RRT index metrics")

    args = parser.parse_args()
    db = NephroGuardDB()

    if args.cmd == "formulary":
        print(f"{'ID':<24} {'Medication':<38} {'Primary Renal Metric':<32} {'Sick-Day Hold'}")
        print("-" * 112)
        for k, v in FORMULARY.items():
            print(
                f"{k:<24} {v['name']:<38} {v['index_metric']:<32} {'YES' if v.get('sick_day_hold') else 'No'}"
            )
        return 0

    if args.cmd == "list-ward":
        patients = db.list_patients()
        print(
            f"{'ID':<26} {'Patient Name':<20} {'Room':<14} {'CG CrCl':<10} {'keGFR':<10} {'eGFR Idx':<10} {'RRT':<8} {'Safety':<8} {'I-PASS Severity'}"
        )
        print("-" * 140)
        for p in patients:
            ev = evaluate_full_patient_case(p)
            k = ev["kinetics"]
            print(
                f"{p['id']:<26} {p['name']:<20} {p['room']:<14} "
                f"{str(k['crcl_selected']):<10} {str(k['kegfr_ml_min']):<10} "
                f"{str(k['egfr_indexed']):<10} {k['rrt_modality'].upper():<8} "
                f"{str(ev['safety_score']) + '/100':<8} {ev['ipass']['illness_severity']}"
            )
        return 0

    if args.cmd == "audit":
        p = db.get_patient(args.patient_id)
        if not p:
            print(f"Error: Patient '{args.patient_id}' not found.", file=sys.stderr)
            return 1
        ev = evaluate_full_patient_case(p)
        if args.format == "json":
            print(json.dumps(ev, indent=2))
        elif args.format == "ipass":
            print(ev["ipass"]["markdown"])
        elif args.format == "fhir":
            print(json.dumps(ev["fhir_bundle"], indent=2))
        elif args.format.startswith("handout-"):
            lang = args.format.split("-")[1]
            print(ev["patient_handout"][lang])
        else:
            k = ev["kinetics"]
            print("=" * 94)
            print(f"NEPHROGUARD v3.0 CLINICAL AUDIT: {p['name']} ({p['room']}) — {p['primary_diagnosis']}")
            print("=" * 94)
            print(
                f"Anthropometrics : {k['age']:.0f}yo {k['sex']} | Wt: {k['weight_kg']} kg | Ht: {k['height_cm']} cm | "
                f"BMI: {k['bmi']} kg/m2 | BSA: {k['bsa_m2']} m2"
            )
            print(
                f"Clearance Matrix: CG CrCl ({k['selected_weight_basis']}): {k['crcl_selected']} mL/min | "
                f"Chen keGFR: {k['kegfr_ml_min']} mL/min | Effective Dosing CrCl: {k['effective_dosing_crcl']} mL/min"
            )
            print(
                f"CKD-EPI Equations: 2021 Cr Indexed: {k['egfr_indexed']} | BSA De-Indexed: {k['egfr_non_indexed']} | "
                f"2021 Cr-Cys Combined: {k['egfr_cr_cys_indexed'] or 'N/A'}"
            )
            print(
                f"Renal & RRT     : KDIGO {k['kdigo_stage']} | {k['aki_stage']} | RRT: {k['rrt_modality'].upper()} | "
                f"Serum K+: {k['potassium_meq_l']} mEq/L | Safety Score: {ev['safety_score']}/100"
            )
            if ev["syndromes"]:
                print("\n--- MULTI-DRUG SYNDROME ALERTS ---")
                for s in ev["syndromes"]:
                    print(f"* [{s['severity']}] {s['title']}")
                    print(f"  Action: {s['management']}")
            print("\n--- MEDICATION RECONCILIATION ---")
            for d in ev["drug_evaluations"]:
                print(
                    f"* {d['name']} [{d['status']}] (t1/2: {d['normal_half_life_h']}h -> {d['est_half_life_h']}h)"
                )
                print(f"  Ordered: {d['current_dose']}  ==>  Recommended: {d['recommended_regimen']}")
            print("\n" + ev["ipass"]["markdown"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
