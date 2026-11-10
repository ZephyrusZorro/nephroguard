"""
NephroGuard & ShiftPass v3.0 — Core Clinical Renal Pharmacokinetics, Kinetic eGFR (keGFR),
2021 CKD-EPI Creatinine-Cystatin C, Renal Replacement Therapy (IHD/PD/CRRT),
30-Drug Nephrotoxicity & Syndrome Engine, I-PASS Handoff, Multilingual Patient Handout,
and HL7 FHIR R4 Interoperability Module.

Verified Equations & References:
- Chen (2013) Kinetic eGFR (keGFR): J Am Soc Nephrol (https://pubmed.ncbi.nlm.nih.gov/23704286/) & RenalCareMatters (https://renalcarematters.com/guides/calc-kegfr)
- 2021 CKD-EPI Creatinine & Combined Creatinine-Cystatin C (Race-Free): NIDDK / NKF (https://www.niddk.nih.gov/research-funding/research-programs/kidney-clinical-research-epidemiology/laboratory/glomerular-filtration-rate-equations/adults)
- BSA De-Indexing (eGFR_non_indexed = eGFR_indexed * BSA / 1.73): Eur J Clin Pharmacol (https://pmc.ncbi.nlm.nih.gov/articles/PMC7481157/)
- Cockcroft-Gault Creatinine Clearance & Devine IBW / Adjusted Body Weight (0.4 factor): MetricGate / MedCalc-Bench (https://metricgate.com/docs/cockcroft-gault-creatinine/)
- Continuous Renal Replacement Therapy (CRRT) Antimicrobial Dosing: Frontiers in Pharmacology (https://pmc.ncbi.nlm.nih.gov/articles/PMC7273837/) & UNMC ASP (https://www.unmc.edu/intmed/_documents/id/asp/final_crrt_pirrt_abxrecommendations_2023.pdf)
- KDIGO 2024 CKD Staging & AKI Kinetic Criteria: KDIGO Guidelines (https://kdigo.org/wp-content/uploads/2024/03/KDIGO-2024-CKD-Guideline.pdf)
- Triple Whammy AKI Mechanism: bpac.org.nz / PMC9889944 (https://bpac.org.nz/2018/triple-whammy.aspx)
- DDInter 2.0 Drug Interaction & Therapeutic Duplication Rules: Nucleic Acids Res 2025 (https://pmc.ncbi.nlm.nih.gov/articles/PMC11701621/)
- I-PASS Clinical Handoff Framework: BMJ Open Quality / CASRAI (https://pmc.ncbi.nlm.nih.gov/articles/PMC12458891/)
"""

from __future__ import annotations
import html
import math
import time
from typing import Any, Dict, List, Optional


FORMULARY: Dict[str, Dict[str, Any]] = {
    "apixaban": {
        "id": "apixaban",
        "name": "Apixaban (Eliquis)",
        "category": "Anticoagulant (Factor Xa Inhibitor)",
        "therapeutic_class": "anticoagulant",
        "index_metric": "ABC Criteria & CrCl (CG)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": True,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "5 mg PO BID",
        "ihd_dose": "2.5 mg PO BID (if Age >=80 or Wt <=60kg; else 5 mg BID per FDA label)",
        "pd_dose": "2.5 mg PO BID (Use with caution; limited PD data)",
        "crrt_dose": "2.5-5 mg PO BID (Not significantly cleared by CRRT; monitor anti-Xa)",
        "source_title": "FDA DailyMed: Eliquis (Apixaban) Label",
        "source_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=1523ab32-2c2c-6501-e063-6394a90aa0b3",
        "half_life_normal_h": 12.0,
        "half_life_esrd_h": 17.5,
    },
    "rivaroxaban": {
        "id": "rivaroxaban",
        "name": "Rivaroxaban (Xarelto)",
        "category": "Anticoagulant (Factor Xa Inhibitor)",
        "therapeutic_class": "anticoagulant",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": True,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "20 mg PO daily with evening meal",
        "ihd_dose": "AVOID / Contraindicated in IHD (Switch to Apixaban or Warfarin)",
        "pd_dose": "AVOID / Contraindicated in PD",
        "crrt_dose": "AVOID in CRRT (Use unfractionated heparin or adjusted alternative)",
        "source_title": "Rivaroxaban Clinical Pharmacology & FDA Renal Dosing",
        "source_url": "https://elicit.com/mechanism-of-action/rivaroxaban",
        "half_life_normal_h": 8.0,
        "half_life_esrd_h": 13.0,
    },
    "enoxaparin": {
        "id": "enoxaparin",
        "name": "Enoxaparin (Lovenox)",
        "category": "Anticoagulant (Low Molecular Weight Heparin)",
        "therapeutic_class": "anticoagulant",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": True,
        "bleed_risk": True,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "1 mg/kg SC q12h (Treatment) or 40 mg SC q24h (Prophylaxis)",
        "ihd_dose": "AVOID for treatment (Switch to UFH); Prophylaxis: 30 mg SC q24h",
        "pd_dose": "Prophylaxis: 30 mg SC q24h; Treatment: 1 mg/kg SC q24h with anti-Xa monitoring",
        "crrt_dose": "Prophylaxis: 30-40 mg SC q24h; Treatment: Prefer IV UFH or 0.5-1 mg/kg q12-24h by anti-Xa",
        "source_title": "Enoxaparin Renal Dosing Guidelines (CrCl <30 mL/min)",
        "source_url": "https://medicaldialogues.in/generics/enoxaparin-2722132",
        "half_life_normal_h": 4.5,
        "half_life_esrd_h": 11.0,
    },
    "dabigatran": {
        "id": "dabigatran",
        "name": "Dabigatran (Pradaxa)",
        "category": "Anticoagulant (Direct Thrombin Inhibitor)",
        "therapeutic_class": "anticoagulant",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": True,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "150 mg PO BID",
        "ihd_dose": "CONTRAINDICATED in IHD (>80% renal clearance; severe bleed risk)",
        "pd_dose": "CONTRAINDICATED in PD",
        "crrt_dose": "CONTRAINDICATED in CRRT",
        "source_title": "RACGP Prescribing in Chronic Renal Impairment",
        "source_url": "https://www.racgp.org.au/afp/2013/january-february/prescribing-for-older-people-with-cri",
        "half_life_normal_h": 13.0,
        "half_life_esrd_h": 28.0,
    },
    "metformin": {
        "id": "metformin",
        "name": "Metformin (Glucophage)",
        "category": "Antidiabetic (Biguanide)",
        "therapeutic_class": "biguanide",
        "index_metric": "eGFR (CKD-EPI Indexed)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "1000 mg PO BID",
        "ihd_dose": "CONTRAINDICATED in IHD (Lactic acidosis risk)",
        "pd_dose": "CONTRAINDICATED in PD (Lactic acidosis risk)",
        "crrt_dose": "CONTRAINDICATED in CRRT / ICU AKI",
        "source_title": "FDA DailyMed: Metformin HCl Renal & Lactic Acidosis Warning",
        "source_url": "https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid=2ffeb25a-76a9-01e6-e063-6394a90ae332",
        "half_life_normal_h": 6.2,
        "half_life_esrd_h": 19.0,
    },
    "sitagliptin": {
        "id": "sitagliptin",
        "name": "Sitagliptin (Januvia)",
        "category": "Antidiabetic (DPP-4 Inhibitor)",
        "therapeutic_class": "dpp4_inhibitor",
        "index_metric": "eGFR (CKD-EPI Indexed)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "100 mg PO daily",
        "ihd_dose": "25 mg PO once daily (Administer without regard to hemodialysis timing)",
        "pd_dose": "25 mg PO once daily",
        "crrt_dose": "50 mg PO once daily",
        "source_title": "FDA Renal Dose Adjustment Guide",
        "source_url": "https://calculate.medsyncpro.org/renal-dose-adjustment-guide/",
        "half_life_normal_h": 12.4,
        "half_life_esrd_h": 28.0,
    },
    "gabapentin": {
        "id": "gabapentin",
        "name": "Gabapentin (Neurontin)",
        "category": "Anticonvulsant / Neuropathic Analgesic",
        "therapeutic_class": "gabapentinoid",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "600 mg PO TID (1800 mg/day)",
        "ihd_dose": "100-300 mg PO load, then 125-350 mg PO post-hemodialysis only (3x/week)",
        "pd_dose": "100-300 mg PO q48h",
        "crrt_dose": "200-300 mg PO BID (Significant dialytic clearance during CRRT)",
        "source_title": "FDA Neurontin (Gabapentin) Prescribing Information",
        "source_url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2025/020235s079,020882s060,021129s059lbl.pdf",
        "half_life_normal_h": 6.5,
        "half_life_esrd_h": 52.0,
    },
    "pregabalin": {
        "id": "pregabalin",
        "name": "Pregabalin (Lyrica)",
        "category": "Anticonvulsant / Neuropathic Analgesic",
        "therapeutic_class": "gabapentinoid",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "150 mg PO BID",
        "ihd_dose": "25-75 mg PO q24h + 25-100 mg supplemental dose immediately post-HD",
        "pd_dose": "25-75 mg PO q24h",
        "crrt_dose": "75-150 mg PO daily (or 50-75 mg PO BID)",
        "source_title": "Evaluation of Gabapentin & Pregabalin in Hospitalized Patients (PMC10838538)",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC10838538/",
        "half_life_normal_h": 6.3,
        "half_life_esrd_h": 48.0,
    },
    "vancomycin": {
        "id": "vancomycin",
        "name": "Vancomycin (IV)",
        "category": "Glycopeptide Antibiotic",
        "therapeutic_class": "glycopeptide",
        "index_metric": "CrCl (Cockcroft-Gault) & TDM",
        "nephrotoxic": True,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "15 mg/kg IV q12h (AUC24/MIC target 400-600)",
        "ihd_dose": "Load 20-25 mg/kg IV x1, then 7.5-10 mg/kg IV post-HD based on pre-HD serum level",
        "pd_dose": "Load 15-20 mg/kg IV x1, then redose every 3-5 days by serum trough",
        "crrt_dose": "Load 20-25 mg/kg IV x1, then 7.5-10 mg/kg IV q12h (or 15 mg/kg q24h if effluent <20 mL/kg/h) with TDM",
        "source_title": "Nebraska Medicine Anti-Infective Renal & CRRT Dosing Protocol",
        "source_url": "https://www.nebraskamed.com/sites/default/files/documents/for-providers/asp/tnmc-anti-infective-renal-dosing-guidelines.pdf",
        "half_life_normal_h": 6.0,
        "half_life_esrd_h": 120.0,
    },
    "cefepime": {
        "id": "cefepime",
        "name": "Cefepime (Maxipime)",
        "category": "4th-Gen Cephalosporin Antibiotic",
        "therapeutic_class": "beta_lactam",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "2 g IV q8h",
        "ihd_dose": "1 g IV q24h (Give after hemodialysis on dialysis days; or 2 g IV 3x/week post-HD)",
        "pd_dose": "1-2 g IV q48h",
        "crrt_dose": "2 g IV load, then 1-2 g IV q12h (or 2 g IV q8h if CRRT effluent >=30 mL/kg/h)",
        "source_title": "Nebraska Medicine Anti-Infective Renal Dosing Protocol",
        "source_url": "https://www.nebraskamed.com/sites/default/files/documents/for-providers/asp/tnmc-anti-infective-renal-dosing-guidelines.pdf",
        "half_life_normal_h": 2.0,
        "half_life_esrd_h": 18.0,
    },
    "meropenem": {
        "id": "meropenem",
        "name": "Meropenem (Merrem)",
        "category": "Carbapenem Antibiotic",
        "therapeutic_class": "beta_lactam",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "1 g IV q8h",
        "ihd_dose": "500 mg IV q24h (Administer after hemodialysis on HD days)",
        "pd_dose": "500 mg IV q24h",
        "crrt_dose": "1 g IV q8h (if effluent >=25 mL/kg/h) or 1 g IV q12h (if effluent <25 mL/kg/h)",
        "source_title": "Meropenem & Piperacillin/Tazobactam CRRT Dosing (PMC12405346)",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12405346/",
        "half_life_normal_h": 1.0,
        "half_life_esrd_h": 10.0,
    },
    "piperacillin_tazobactam": {
        "id": "piperacillin_tazobactam",
        "name": "Piperacillin-Tazobactam (Zosyn)",
        "category": "Antipseudomonal Penicillin + Beta-Lactamase Inhibitor",
        "therapeutic_class": "beta_lactam",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": True,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "4.5 g IV q6h (or 3.375 g IV q6h)",
        "ihd_dose": "2.25 g IV q12h (or q8h for Pseudomonas) + 0.75 g supplemental dose post-HD",
        "pd_dose": "2.25 g IV q8-12h",
        "crrt_dose": "3.375 g IV q6h (or 4.5 g IV q8h extended infusion for Pseudomonas in CRRT)",
        "source_title": "Recommendation of Antimicrobial Dosing During CRRT (PMC7273837)",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC7273837/",
        "half_life_normal_h": 1.0,
        "half_life_esrd_h": 5.0,
    },
    "ciprofloxacin": {
        "id": "ciprofloxacin",
        "name": "Ciprofloxacin (Cipro)",
        "category": "Fluoroquinolone Antibiotic",
        "therapeutic_class": "fluoroquinolone",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": True,
        "sick_day_hold": False,
        "standard_dose": "500 mg PO q12h (or 400 mg IV q8-12h)",
        "ihd_dose": "250-500 mg PO q24h (or 200-400 mg IV q24h; administer post-HD)",
        "pd_dose": "250-500 mg PO q24h",
        "crrt_dose": "400 mg IV q12h (or 500 mg PO q12h)",
        "source_title": "Antimicrobial Dosing in Critically Ill AKI (WJGNet)",
        "source_url": "https://www.wjgnet.com/2220-6124/full/v14/i3/102667.htm",
        "half_life_normal_h": 4.0,
        "half_life_esrd_h": 8.5,
    },
    "levofloxacin": {
        "id": "levofloxacin",
        "name": "Levofloxacin (Levaquin)",
        "category": "Fluoroquinolone Antibiotic",
        "therapeutic_class": "fluoroquinolone",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": True,
        "sick_day_hold": False,
        "standard_dose": "750 mg PO/IV q24h",
        "ihd_dose": "750 mg x1 load, then 500 mg PO/IV q48h (No supplemental post-HD dose needed)",
        "pd_dose": "750 mg x1 load, then 500 mg PO/IV q48h",
        "crrt_dose": "750 mg IV/PO x1 load, then 500 mg q24h (or 750 mg q48h)",
        "source_title": "MedCentral Levofloxacin Clinical Monograph",
        "source_url": "https://www.medcentral.com/drugs/monograph/14495-397040/levofloxacin-oral",
        "half_life_normal_h": 7.0,
        "half_life_esrd_h": 35.0,
    },
    "tmp_smx": {
        "id": "tmp_smx",
        "name": "Trimethoprim-Sulfamethoxazole (Bactrim DS)",
        "category": "Sulfonamide / Folate Antagonist Antibiotic",
        "therapeutic_class": "sulfonamide",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": True,
        "hyperkalemic": True,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "1 DS tablet (800/160 mg) PO q12h",
        "ihd_dose": "AVOID unless PJP/Stenotrophomonas (If required: 2.5-5 mg/kg TMP q24h post-HD)",
        "pd_dose": "AVOID or 1 SS tablet PO q24h with strict K+ monitoring",
        "crrt_dose": "5 mg/kg (TMP component) IV/PO q12h (for severe infection/PJP; monitor K+ daily)",
        "source_title": "Nebraska Medicine Antimicrobial Renal Dosing Guidelines",
        "source_url": "https://www.nebraskamed.com/sites/default/files/documents/for-providers/asp/nm-anti-infective-renal-dosing-guidelines.pdf",
        "half_life_normal_h": 10.0,
        "half_life_esrd_h": 30.0,
    },
    "acyclovir": {
        "id": "acyclovir",
        "name": "Acyclovir (IV / High-Dose)",
        "category": "Antiviral (Nucleoside Analog)",
        "therapeutic_class": "antiviral",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": True,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "5-10 mg/kg IV q8h",
        "ihd_dose": "2.5-5 mg/kg AdjBW IV q24h (Administer after hemodialysis on HD days)",
        "pd_dose": "2.5-5 mg/kg AdjBW IV q24h",
        "crrt_dose": "5-10 mg/kg AdjBW IV q12-24h (depending on HSV encephalitis vs mucocutaneous)",
        "source_title": "Renal Antimicrobial Dosage Guidelines",
        "source_url": "https://www.scribd.com/document/935069076/Antibiotic-Dosing",
        "half_life_normal_h": 2.5,
        "half_life_esrd_h": 20.0,
    },
    "lisinopril": {
        "id": "lisinopril",
        "name": "Lisinopril (Prinivil / Zestril)",
        "category": "ACE Inhibitor (RAAS Blocker)",
        "therapeutic_class": "raas_inhibitor",
        "index_metric": "CrCl (Cockcroft-Gault) & AKI Status",
        "nephrotoxic": True,
        "hyperkalemic": True,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "10-40 mg PO daily",
        "ihd_dose": "2.5-5 mg PO once daily (Give post-HD to avoid intradialytic hypotension)",
        "pd_dose": "2.5-5 mg PO once daily",
        "crrt_dose": "HOLD during acute CRRT / hemodynamic instability",
        "source_title": "bpac.org.nz: Avoiding the Triple Whammy in Primary Care",
        "source_url": "https://bpac.org.nz/2018/triple-whammy.aspx",
        "half_life_normal_h": 12.0,
        "half_life_esrd_h": 42.0,
    },
    "losartan": {
        "id": "losartan",
        "name": "Losartan (Cozaar)",
        "category": "Angiotensin Receptor Blocker (RAAS Blocker)",
        "therapeutic_class": "raas_inhibitor",
        "index_metric": "CrCl (Cockcroft-Gault) & AKI Status",
        "nephrotoxic": True,
        "hyperkalemic": True,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "50-100 mg PO daily",
        "ihd_dose": "25-50 mg PO once daily (Not dialyzed; monitor K+)",
        "pd_dose": "25-50 mg PO once daily",
        "crrt_dose": "HOLD during acute CRRT / hemodynamic instability",
        "source_title": "bpac.org.nz: Avoiding the Triple Whammy in Primary Care",
        "source_url": "https://bpac.org.nz/2018/triple-whammy.aspx",
        "half_life_normal_h": 6.0,
        "half_life_esrd_h": 9.0,
    },
    "spironolactone": {
        "id": "spironolactone",
        "name": "Spironolactone (Aldactone)",
        "category": "Mineralocorticoid Receptor Antagonist / K+-Sparing Diuretic",
        "therapeutic_class": "k_sparing_diuretic",
        "index_metric": "eGFR / CrCl & Serum K+",
        "nephrotoxic": False,
        "hyperkalemic": True,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "25 mg PO daily",
        "ihd_dose": "AVOID / Contraindicated in ESRD/IHD due to fatal hyperkalemia risk",
        "pd_dose": "12.5-25 mg PO daily ONLY if hypokalemic on PD; otherwise AVOID",
        "crrt_dose": "CONTRAINDICATED / HOLD in CRRT",
        "source_title": "RACGP Prescribing in Chronic Renal Impairment",
        "source_url": "https://www.racgp.org.au/afp/2013/january-february/prescribing-for-older-people-with-cri",
        "half_life_normal_h": 15.0,
        "half_life_esrd_h": 36.0,
    },
    "furosemide": {
        "id": "furosemide",
        "name": "Furosemide (Lasix)",
        "category": "Loop Diuretic",
        "therapeutic_class": "diuretic",
        "index_metric": "CrCl & Volume Status",
        "nephrotoxic": True,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "20-80 mg PO/IV daily or BID",
        "ihd_dose": "80-200 mg PO daily ONLY if residual urine output >200 mL/d; else discontinue",
        "pd_dose": "80-160 mg PO daily to preserve residual renal volume status",
        "crrt_dose": "HOLD during CRRT (Ultrafiltration managed mechanically via CRRT machine)",
        "source_title": "PDR.Net Furosemide Clinical Dosing Summary",
        "source_url": "https://www.pdr.net/drug-summary/Furosemide-Injection-furosemide-1557",
        "half_life_normal_h": 1.5,
        "half_life_esrd_h": 9.0,
    },
    "ibuprofen": {
        "id": "ibuprofen",
        "name": "Ibuprofen (Motrin / Advil)",
        "category": "Non-Steroidal Anti-Inflammatory Drug (NSAID)",
        "therapeutic_class": "nsaid",
        "index_metric": "eGFR / CrCl",
        "nephrotoxic": True,
        "hyperkalemic": True,
        "bleed_risk": True,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "400-600 mg PO q6-8h PRN",
        "ihd_dose": "AVOID (Destroys residual renal function and increases GI bleed risk in uremia)",
        "pd_dose": "CONTRAINDICATED in PD (Destroys residual renal clearance)",
        "crrt_dose": "CONTRAINDICATED in CRRT / ICU AKI",
        "source_title": "Triple Whammy Acute Kidney Injury (PMC9889944)",
        "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC9889944/",
        "half_life_normal_h": 2.0,
        "half_life_esrd_h": 3.5,
    },
    "ketorolac": {
        "id": "ketorolac",
        "name": "Ketorolac (Toradol)",
        "category": "Parenteral / Oral NSAID",
        "therapeutic_class": "nsaid",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": True,
        "hyperkalemic": True,
        "bleed_risk": True,
        "qt_prolonging": False,
        "sick_day_hold": True,
        "standard_dose": "30 mg IV q6h (Max 5 days)",
        "ihd_dose": "CONTRAINDICATED (Boxed warning for advanced renal impairment & bleeding)",
        "pd_dose": "CONTRAINDICATED",
        "crrt_dose": "CONTRAINDICATED",
        "source_title": "Rational Drug Use in Chronic Kidney Disease Guidelines",
        "source_url": "https://www.ramacnec.com/AD/DocumentFile/20240329074308_File_Updated%20RDU%20in%20Chronic%20disease%202024.pdf",
        "half_life_normal_h": 5.5,
        "half_life_esrd_h": 14.0,
    },
    "allopurinol": {
        "id": "allopurinol",
        "name": "Allopurinol (Zyloprim)",
        "category": "Xanthine Oxidase Inhibitor (Antigout)",
        "therapeutic_class": "xanthine_oxidase_inhibitor",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "300 mg PO daily",
        "ihd_dose": "100 mg PO post-hemodialysis (3x/week) or 50 mg PO daily",
        "pd_dose": "50 mg PO q24-48h",
        "crrt_dose": "100 mg PO daily",
        "source_title": "RACGP Prescribing in Chronic Renal Impairment",
        "source_url": "https://www.racgp.org.au/afp/2013/january-february/prescribing-for-older-people-with-cri",
        "half_life_normal_h": 15.0,
        "half_life_esrd_h": 70.0,
    },
    "morphine": {
        "id": "morphine",
        "name": "Morphine (IV / PO)",
        "category": "Opioid Analgesic",
        "therapeutic_class": "opioid",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "4-8 mg IV q4h PRN or 15-30 mg PO q4h",
        "ihd_dose": "AVOID (Active M6G/M3G glucuronides accumulate causing delayed narcosis; use Fentanyl)",
        "pd_dose": "AVOID (Switch to Fentanyl or low-dose Hydromorphone)",
        "crrt_dose": "AVOID (Prefer Fentanyl IV infusion/bolus in CRRT)",
        "source_title": "Rational Drug Use in CKD: Opioid Metabolite Accumulation",
        "source_url": "https://www.ramacnec.com/AD/DocumentFile/20240329074308_File_Updated%20RDU%20in%20Chronic%20disease%202024.pdf",
        "half_life_normal_h": 3.0,
        "half_life_esrd_h": 40.0,
    },
    # --- 6 NEW HIGH-RISK DRUGS ADDED IN v3.0 (Total 30) ---
    "gentamicin": {
        "id": "gentamicin",
        "name": "Gentamicin (IV)",
        "category": "Aminoglycoside Antibiotic",
        "therapeutic_class": "aminoglycoside",
        "index_metric": "CrCl (Cockcroft-Gault) & TDM",
        "nephrotoxic": True,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "5-7 mg/kg AdjBW IV q24h (Extended-Interval)",
        "ihd_dose": "1.5-2 mg/kg AdjBW IV post-HD, redose by pre-/post-HD serum concentrations",
        "pd_dose": "1.5-2 mg/kg AdjBW IV q48h by serum TDM",
        "crrt_dose": "2.5-3 mg/kg AdjBW IV q24-48h with peak/trough TDM",
        "source_title": "MGB / Nebraska Medicine Aminoglycoside Renal Dosing Guidelines",
        "source_url": "https://mghwhitebook.app/MGBAntimicrobialDosing",
        "half_life_normal_h": 2.5,
        "half_life_esrd_h": 50.0,
    },
    "amikacin": {
        "id": "amikacin",
        "name": "Amikacin (IV)",
        "category": "Aminoglycoside Antibiotic",
        "therapeutic_class": "aminoglycoside",
        "index_metric": "CrCl (Cockcroft-Gault) & TDM",
        "nephrotoxic": True,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "15-20 mg/kg AdjBW IV q24h",
        "ihd_dose": "5-7.5 mg/kg AdjBW IV post-HD, redose by serum concentrations",
        "pd_dose": "5-7.5 mg/kg AdjBW IV q48h by serum TDM",
        "crrt_dose": "7.5-10 mg/kg AdjBW IV q24-48h with peak/trough TDM",
        "source_title": "MGB Antimicrobial Dosing Guidelines",
        "source_url": "https://mghwhitebook.app/MGBAntimicrobialDosing",
        "half_life_normal_h": 2.5,
        "half_life_esrd_h": 55.0,
    },
    "colchicine": {
        "id": "colchicine",
        "name": "Colchicine (Colcrys)",
        "category": "Antigout / Anti-Inflammatory Tubulin Inhibitor",
        "therapeutic_class": "antigout_colchicine",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "0.6 mg PO BID (Prophylaxis) or 1.2 mg then 0.6 mg 1h later (Flare)",
        "ihd_dose": "Prophylaxis: 0.3 mg PO twice weekly; Acute flare: 0.6 mg PO x1 single dose (Do not repeat for 14d)",
        "pd_dose": "Prophylaxis: 0.3 mg PO twice weekly",
        "crrt_dose": "AVOID in CRRT / multi-organ failure (Neuromyopathy and pancytopenia risk)",
        "source_title": "RACGP Prescribing in Chronic Renal Impairment",
        "source_url": "https://www.racgp.org.au/afp/2013/january-february/prescribing-for-older-people-with-cri",
        "half_life_normal_h": 26.0,
        "half_life_esrd_h": 65.0,
    },
    "fluconazole": {
        "id": "fluconazole",
        "name": "Fluconazole (Diflucan)",
        "category": "Triazole Antifungal",
        "therapeutic_class": "antifungal_azole",
        "index_metric": "CrCl (Cockcroft-Gault) & CRRT Tubular Reabsorption",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": True,
        "sick_day_hold": False,
        "standard_dose": "400 mg PO/IV q24h (After 800 mg load)",
        "ihd_dose": "200 mg PO/IV q24h (or 400 mg post-HD 3x/week)",
        "pd_dose": "200 mg PO/IV q24h",
        "crrt_dose": "800 mg load, then 400-600 mg IV q24h (CRRT lacks physiological tubular reabsorption of fluconazole!)",
        "source_title": "UNMC / Nebraska Medicine CRRT Antimicrobial Dosing Guidelines",
        "source_url": "https://www.unmc.edu/intmed/_documents/id/asp/final_crrt_pirrt_abxrecommendations_2023.pdf",
        "half_life_normal_h": 30.0,
        "half_life_esrd_h": 98.0,
    },
    "digoxin": {
        "id": "digoxin",
        "name": "Digoxin (Lanoxin)",
        "category": "Cardiac Glycoside (Inotrope / AV Nodal Blocker)",
        "therapeutic_class": "cardiac_glycoside",
        "index_metric": "CrCl (Cockcroft-Gault) & Serum K+",
        "nephrotoxic": False,
        "hyperkalemic": True,
        "bleed_risk": False,
        "qt_prolonging": False,
        "sick_day_hold": False,
        "standard_dose": "0.125-0.25 mg PO daily",
        "ihd_dose": "0.0625 mg PO q48h (Reduce loading dose by 50% due to decreased Vd in ESRD; check trough 0.5-0.9 ng/mL)",
        "pd_dose": "0.0625 mg PO q48h",
        "crrt_dose": "0.0625 mg IV/PO q24-48h with strict serum digoxin and K+/Mg2+ monitoring",
        "source_title": "Rhode Island APRN Prescribing Pharmacology & Digoxin Renal Toxicity",
        "source_url": "https://nursingcecentral.com/lessons/rhode-island-aprn-prescribing-renewal-pharmacology-bundle/",
        "half_life_normal_h": 36.0,
        "half_life_esrd_h": 110.0,
    },
    "famotidine": {
        "id": "famotidine",
        "name": "Famotidine (Pepcid)",
        "category": "Histamine H2-Receptor Antagonist",
        "therapeutic_class": "h2_antagonist",
        "index_metric": "CrCl (Cockcroft-Gault)",
        "nephrotoxic": False,
        "hyperkalemic": False,
        "bleed_risk": False,
        "qt_prolonging": True,
        "sick_day_hold": False,
        "standard_dose": "20 mg PO/IV BID",
        "ihd_dose": "20 mg PO/IV q24h or 20 mg q48h (Prevents H2-blocker delirium/confusion in ESRD)",
        "pd_dose": "20 mg PO/IV q24h",
        "crrt_dose": "20 mg IV q24h",
        "source_title": "FDA Renal Dose Adjustment Guide",
        "source_url": "https://calculate.medsyncpro.org/renal-dose-adjustment-guide/",
        "half_life_normal_h": 3.0,
        "half_life_esrd_h": 20.0,
    },
}


def compute_renal_kinetics(
    age: float,
    sex: str,
    weight_kg: float,
    height_cm: float,
    scr_value: float,
    scr_unit: str = "mg_dl",
    baseline_scr_mg_dl: Optional[float] = None,
    potassium_meq_l: float = 4.2,
    weight_override: str = "auto",
    delta_hours: float = 24.0,
    cystatin_c_mg_l: Optional[float] = None,
    rrt_modality: str = "none",
    crrt_effluent_ml_kg_h: float = 25.0,
) -> Dict[str, Any]:
    """
    Computes BMI, Mosteller BSA, Devine IBW, AdjBW (0.4 factor), Cockcroft-Gault CrCl,
    2021 CKD-EPI eGFR (indexed & BSA de-indexed), 2021 CKD-EPI Combined Creatinine-Cystatin C
    (when Cystatin C is provided), Chen (2013) Kinetic eGFR (keGFR), RRT/CRRT effective clearance,
    KDIGO stage, and AKI kinetics.
    """
    if age < 18 or age > 120:
        raise ValueError("Adult renal kinetics require age between 18 and 120 years.")
    if weight_kg <= 20 or weight_kg > 350:
        raise ValueError("Weight must be between 20 and 350 kg.")
    if height_cm <= 100 or height_cm > 250:
        raise ValueError("Height must be between 100 and 250 cm.")
    if scr_value <= 0:
        raise ValueError("Serum creatinine must be greater than 0.")

    sex_norm = sex.strip().lower()
    is_female = sex_norm in ("female", "f")
    is_umol = scr_unit.lower() in ("umol_l", "umol/l")

    scr_mg_dl = scr_value / 88.42 if is_umol else float(scr_value)
    if scr_mg_dl <= 0.1 or scr_mg_dl > 25.0:
        raise ValueError("Normalized serum creatinine (mg/dL) must be between 0.1 and 25.0.")

    # Bug 1 Fix: If baseline_scr_mg_dl was entered in umol/L (>25), auto-convert to mg/dL
    base_scr_norm: Optional[float] = None
    if baseline_scr_mg_dl is not None and baseline_scr_mg_dl > 0:
        base_scr_norm = (
            float(baseline_scr_mg_dl) / 88.42
            if float(baseline_scr_mg_dl) > 25.0
            else float(baseline_scr_mg_dl)
        )

    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m * height_m)
    bsa_m2 = math.sqrt((height_cm * weight_kg) / 3600.0)

    height_inches = height_cm / 2.54
    inches_over_60 = max(0.0, height_inches - 60.0)
    ibw_kg = (45.5 if is_female else 50.0) + 2.3 * inches_over_60
    adjbw_kg = ibw_kg + 0.4 * (weight_kg - ibw_kg)

    if weight_kg < ibw_kg:
        recommended_weight_basis = "ABW"
        recommended_weight_kg = weight_kg
        weight_rationale = "Actual Body Weight (ABW < IBW: underweight/sarcopenic protection)"
    elif bmi >= 30.0 or weight_kg > 1.25 * ibw_kg:
        recommended_weight_basis = "AdjBW"
        recommended_weight_kg = adjbw_kg
        weight_rationale = "Adjusted Body Weight (IBW + 0.4*(ABW-IBW) for BMI >= 30 or ABW > 125% IBW)"
    else:
        recommended_weight_basis = "IBW"
        recommended_weight_kg = ibw_kg
        weight_rationale = "Ideal Body Weight (Devine formula standard for non-obese adults with ABW >= IBW)"

    if weight_override in ("ABW", "IBW", "AdjBW"):
        selected_basis = weight_override
        selected_weight_kg = (
            weight_kg if weight_override == "ABW" else (ibw_kg if weight_override == "IBW" else adjbw_kg)
        )
    else:
        selected_basis = recommended_weight_basis
        selected_weight_kg = recommended_weight_kg

    sex_factor_cg = 0.85 if is_female else 1.0

    def _cg(wt: float, s_cr: float) -> float:
        return ((140.0 - age) * wt * sex_factor_cg) / (72.0 * s_cr)

    crcl_abw = _cg(weight_kg, scr_mg_dl)
    crcl_ibw = _cg(ibw_kg, scr_mg_dl)
    crcl_adjbw = _cg(adjbw_kg, scr_mg_dl)
    crcl_selected = _cg(selected_weight_kg, scr_mg_dl)

    # 2021 CKD-EPI Creatinine (Race-Free)
    kappa = 0.7 if is_female else 0.9
    alpha = -0.241 if is_female else -0.302
    sex_mult_ckd = 1.012 if is_female else 1.0

    def _ckd_epi_cr(s_cr: float) -> float:
        ratio = s_cr / kappa
        return (
            142.0
            * (min(ratio, 1.0) ** alpha)
            * (max(ratio, 1.0) ** -1.200)
            * (0.9938 ** age)
            * sex_mult_ckd
        )

    egfr_indexed = _ckd_epi_cr(scr_mg_dl)
    egfr_non_indexed = egfr_indexed * (bsa_m2 / 1.73)

    # 2021 CKD-EPI Combined Creatinine-Cystatin C Equation (NIDDK)
    egfr_cr_cys_indexed: Optional[float] = None
    egfr_cr_cys_non_indexed: Optional[float] = None
    if cystatin_c_mg_l is not None and float(cystatin_c_mg_l) > 0.1:
        scys = float(cystatin_c_mg_l)
        r_cr = scr_mg_dl / kappa
        r_cys = scys / 0.8
        sex_mult_comb = 0.963 if is_female else 1.0
        egfr_cr_cys_indexed = (
            135.0
            * (min(r_cr, 1.0) ** alpha)
            * (max(r_cr, 1.0) ** -0.544)
            * (min(r_cys, 1.0) ** -0.323)
            * (max(r_cys, 1.0) ** -0.778)
            * (0.9961 ** age)
            * sex_mult_comb
        )
        egfr_cr_cys_non_indexed = egfr_cr_cys_indexed * (bsa_m2 / 1.73)

    # Chen (2013) Kinetic eGFR (keGFR) for Non-Steady-State Creatinine
    dt_h = max(4.0, float(delta_hours or 24.0))
    if base_scr_norm and base_scr_norm > 0:
        crcl_base = _cg(selected_weight_kg, base_scr_norm)
        scr_mean = (base_scr_norm + scr_mg_dl) / 2.0
        delta_scr = scr_mg_dl - base_scr_norm
        max_delta_scr_per_day = 1.5
        kinetic_factor = 1.0 - (24.0 * delta_scr) / (dt_h * max_delta_scr_per_day)
        kinetic_factor = max(0.05, min(2.0, kinetic_factor))
        kegfr_ml_min = (base_scr_norm * crcl_base / scr_mean) * kinetic_factor
    else:
        kegfr_ml_min = crcl_selected

    # Acute Kidney Injury (AKI) Kinetics Check (KDIGO Criteria)
    aki_detected = False
    aki_stage = "None"
    aki_detail = "Stable renal function relative to baseline."
    if base_scr_norm and base_scr_norm > 0:
        scr_delta = scr_mg_dl - base_scr_norm
        scr_ratio = scr_mg_dl / base_scr_norm
        if scr_ratio >= 3.0 or (scr_mg_dl >= 4.0 and scr_delta >= 0.3):
            aki_detected = True
            aki_stage = "KDIGO AKI Stage 3"
            aki_detail = (
                f"SCr rose from {base_scr_norm:.2f} to {scr_mg_dl:.2f} mg/dL over {dt_h:.0f}h "
                f"({scr_ratio:.2f}x baseline, +{scr_delta:.2f} mg/dL). Chen keGFR is {kegfr_ml_min:.1f} mL/min."
            )
        elif scr_ratio >= 2.0:
            aki_detected = True
            aki_stage = "KDIGO AKI Stage 2"
            aki_detail = (
                f"SCr doubled from {base_scr_norm:.2f} to {scr_mg_dl:.2f} mg/dL over {dt_h:.0f}h "
                f"({scr_ratio:.2f}x baseline). Chen keGFR is {kegfr_ml_min:.1f} mL/min."
            )
        elif scr_delta >= 0.3 or scr_ratio >= 1.5:
            aki_detected = True
            aki_stage = "KDIGO AKI Stage 1"
            aki_detail = (
                f"SCr increased by +{scr_delta:.2f} mg/dL ({scr_ratio:.2f}x baseline) over {dt_h:.0f}h. "
                f"Chen Kinetic eGFR (keGFR) is {kegfr_ml_min:.1f} mL/min (vs static CG {crcl_selected:.1f} mL/min)."
            )

    # Renal Replacement Therapy (RRT) & Effective Dosing Clearance Selection
    rrt_norm = str(rrt_modality or "none").strip().lower()
    if rrt_norm not in ("none", "ihd", "pd", "crrt"):
        rrt_norm = "none"
    effluent_rate = max(10.0, min(60.0, float(crrt_effluent_ml_kg_h or 25.0)))
    crrt_clearance_ml_min = (effluent_rate * weight_kg) / 60.0 if rrt_norm == "crrt" else None

    # Bug 2 Fix: When AKI is present (and not on RRT), use conservative min(crcl_selected, kegfr_ml_min) for safety
    if rrt_norm == "crrt" and crrt_clearance_ml_min is not None:
        effective_dosing_crcl = crrt_clearance_ml_min
    elif rrt_norm in ("ihd", "pd"):
        effective_dosing_crcl = 8.0
    elif aki_detected:
        effective_dosing_crcl = min(crcl_selected, kegfr_ml_min)
    else:
        effective_dosing_crcl = crcl_selected

    # Divergence analysis between Lab eGFR (indexed) and Cockcroft-Gault CrCl (selected)
    abs_divergence = abs(egfr_indexed - crcl_selected)
    pct_divergence = (abs_divergence / max(crcl_selected, 1.0)) * 100.0
    divergence_alert = None
    if pct_divergence >= 25.0 or abs_divergence >= 12.0:
        higher_metric = "Lab eGFR (Indexed)" if egfr_indexed > crcl_selected else "Cockcroft-Gault CrCl"
        divergence_alert = (
            f"Critical Equation Divergence ({pct_divergence:.1f}% / {abs_divergence:.1f} mL/min gap): "
            f"{higher_metric} is substantially higher ({egfr_indexed:.1f} vs {crcl_selected:.1f} mL/min). "
            f"BSA de-indexed eGFR is {egfr_non_indexed:.1f} mL/min and Chen keGFR is {kegfr_ml_min:.1f} mL/min."
        )

    # KDIGO 2024 Staging
    staging_gfr = egfr_cr_cys_indexed if egfr_cr_cys_indexed is not None else egfr_indexed
    if rrt_norm in ("ihd", "pd"):
        kdigo_stage = "G5D"
        kdigo_desc = f"Dialysis-dependent kidney failure ({rrt_norm.upper()})"
    elif staging_gfr >= 90:
        kdigo_stage = "G1"
        kdigo_desc = "Normal or high filtration (>=90 mL/min/1.73m2)"
    elif staging_gfr >= 60:
        kdigo_stage = "G2"
        kdigo_desc = "Mildly decreased filtration (60-89 mL/min/1.73m2)"
    elif staging_gfr >= 45:
        kdigo_stage = "G3a"
        kdigo_desc = "Mild-to-moderately decreased filtration (45-59 mL/min/1.73m2)"
    elif staging_gfr >= 30:
        kdigo_stage = "G3b"
        kdigo_desc = "Moderately-to-severely decreased filtration (30-44 mL/min/1.73m2)"
    elif staging_gfr >= 15:
        kdigo_stage = "G4"
        kdigo_desc = "Severely decreased filtration (15-29 mL/min/1.73m2)"
    else:
        kdigo_stage = "G5"
        kdigo_desc = "Kidney failure (<15 mL/min/1.73m2)"

    return {
        "age": round(age, 1),
        "sex": "Female" if is_female else "Male",
        "weight_kg": round(weight_kg, 1),
        "height_cm": round(height_cm, 1),
        "bmi": round(bmi, 1),
        "bsa_m2": round(bsa_m2, 2),
        "ibw_kg": round(ibw_kg, 1),
        "adjbw_kg": round(adjbw_kg, 1),
        "recommended_weight_basis": recommended_weight_basis,
        "selected_weight_basis": selected_basis,
        "selected_weight_kg": round(selected_weight_kg, 1),
        "weight_rationale": weight_rationale,
        "scr_mg_dl": round(scr_mg_dl, 2),
        "baseline_scr_mg_dl": round(base_scr_norm, 2) if base_scr_norm else None,
        "delta_hours": round(dt_h, 1),
        "cystatin_c_mg_l": round(float(cystatin_c_mg_l), 2) if cystatin_c_mg_l else None,
        "potassium_meq_l": round(potassium_meq_l, 2),
        "rrt_modality": rrt_norm,
        "crrt_effluent_ml_kg_h": round(effluent_rate, 1),
        "crrt_clearance_ml_min": round(crrt_clearance_ml_min, 1) if crrt_clearance_ml_min is not None else None,
        "crcl_abw": round(crcl_abw, 1),
        "crcl_ibw": round(crcl_ibw, 1),
        "crcl_adjbw": round(crcl_adjbw, 1),
        "crcl_selected": round(crcl_selected, 1),
        "kegfr_ml_min": round(kegfr_ml_min, 1),
        "effective_dosing_crcl": round(effective_dosing_crcl, 1),
        "egfr_indexed": round(egfr_indexed, 1),
        "egfr_non_indexed": round(egfr_non_indexed, 1),
        "egfr_cr_cys_indexed": round(egfr_cr_cys_indexed, 1) if egfr_cr_cys_indexed is not None else None,
        "egfr_cr_cys_non_indexed": round(egfr_cr_cys_non_indexed, 1) if egfr_cr_cys_non_indexed is not None else None,
        "abs_divergence": round(abs_divergence, 1),
        "pct_divergence": round(pct_divergence, 1),
        "divergence_alert": divergence_alert,
        "kdigo_stage": kdigo_stage,
        "kdigo_desc": kdigo_desc,
        "aki_detected": aki_detected,
        "aki_stage": aki_stage,
        "aki_detail": aki_detail,
    }


def evaluate_drug_for_patient(
    drug_id: str,
    current_dose: str,
    kinetics: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Evaluates a single medication against the patient's renal kinetics, RRT modality
    (IHD / PD / CRRT), Chen keGFR, ABC criteria, electrolyte status, and AKI state.
    Includes Bug 3 Fix (reconciliation state detection) and Bug 7 Fix (weight-capped loads).
    """
    if drug_id not in FORMULARY:
        raise ValueError(f"Unknown drug_id: {drug_id}")
    info = FORMULARY[drug_id]
    crcl = kinetics["effective_dosing_crcl"]
    egfr = kinetics["egfr_cr_cys_indexed"] if kinetics.get("egfr_cr_cys_indexed") is not None else kinetics["egfr_indexed"]
    age = kinetics["age"]
    wt = kinetics["weight_kg"]
    adj_wt = kinetics["selected_weight_kg"]
    scr = kinetics["scr_mg_dl"]
    k_val = kinetics["potassium_meq_l"]
    aki = kinetics["aki_detected"]
    rrt = kinetics.get("rrt_modality", "none")

    status = "OPTIMAL"
    severity_score = 0
    recommended_regimen = info["standard_dose"]
    clinical_rationale = "Within normal renal dosing parameters."
    action_type = "CONTINUE"

    # Bug 5 Fix: Modality-Specific Renal Replacement Therapy (IHD / PD / CRRT) Override
    if rrt in ("ihd", "pd", "crrt"):
        modality_key = f"{rrt}_dose"
        recommended_regimen = info.get(modality_key, info["standard_dose"])
        upper_rec = recommended_regimen.upper()
        if "CONTRAINDICATED" in upper_rec or "AVOID" in upper_rec or "HOLD" in upper_rec:
            status = "CONTRAINDICATED"
            severity_score = 95
            action_type = "HOLD_OR_SWITCH"
            clinical_rationale = f"Patient is on {rrt.upper()}. {recommended_regimen}"
        else:
            status = "DOSE_REDUCTION_REQUIRED"
            severity_score = 80
            action_type = "RRT_ADJUST"
            crrt_note = (
                f" (CRRT Effluent: {kinetics['crrt_effluent_ml_kg_h']} mL/kg/h -> CL ~{kinetics['crrt_clearance_ml_min']} mL/min)"
                if rrt == "crrt"
                else ""
            )
            clinical_rationale = f"Renal Replacement Therapy ({rrt.upper()}{crrt_note}) requires modality-specific dosing."
    else:
        # Non-RRT Dosing State Machine using effective_dosing_crcl (which incorporates Chen keGFR in AKI)
        if drug_id == "apixaban":
            abc_flags = []
            if age >= 80:
                abc_flags.append(f"Age >=80 ({age:.0f}y)")
            if wt <= 60:
                abc_flags.append(f"Weight <=60kg ({wt:.1f}kg)")
            if scr >= 1.5:
                abc_flags.append(f"SCr >=1.5 ({scr:.2f} mg/dL)")
            if len(abc_flags) >= 2 or crcl < 25:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 85
                recommended_regimen = "2.5 mg PO BID (NVAF stroke prophylaxis)"
                clinical_rationale = (
                    f"Meets >=2 FDA ABC dose-reduction criteria ({', '.join(abc_flags)}) or effective CrCl <25 mL/min "
                    f"({crcl:.1f} mL/min). Standard 5 mg BID doubles major bleeding risk."
                )
                action_type = "REDUCE_DOSE"
            elif len(abc_flags) == 1:
                status = "MONITOR_CLOSELY"
                severity_score = 35
                recommended_regimen = "5 mg PO BID (1 of 3 ABC criteria met; monitor renal trend)"
                clinical_rationale = f"Meets 1 of 3 ABC criteria ({abc_flags[0]}). Dose reduction to 2.5 mg BID requires >=2 criteria."
                action_type = "MONITOR"

        elif drug_id == "rivaroxaban":
            if crcl < 15:
                status = "CONTRAINDICATED"
                severity_score = 95
                recommended_regimen = "AVOID / Discontinue (Switch to adjusted alternative)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<15 mL/min threshold). Rivaroxaban is avoided due to severe accumulation."
                action_type = "HOLD_OR_SWITCH"
            elif crcl <= 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 75
                recommended_regimen = "15 mg PO daily with evening meal (NVAF)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-50 mL/min window). Reduce from 20 mg to 15 mg once daily."
                action_type = "REDUCE_DOSE"

        elif drug_id == "enoxaparin":
            if crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 90
                recommended_regimen = f"1 mg/kg ({round(wt):.0f} mg) SC q24h (Treatment) OR 30 mg SC q24h (Prophylaxis)"
                clinical_rationale = (
                    f"Effective CrCl is {crcl:.1f} mL/min (<30 mL/min threshold). Enoxaparin clearance decreases by 44%; "
                    f"q12h dosing causes severe anti-Xa accumulation and major hemorrhage."
                )
                action_type = "REDUCE_DOSE"

        elif drug_id == "dabigatran":
            if crcl < 15:
                status = "CONTRAINDICATED"
                severity_score = 95
                recommended_regimen = "CONTRAINDICATED (CrCl <15 mL/min)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min. Over 80% renally cleared; life-threatening hemorrhage risk."
                action_type = "HOLD_OR_SWITCH"
            elif crcl <= 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "75 mg PO BID"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-30 mL/min window). Reduce from 150 mg BID to 75 mg BID."
                action_type = "REDUCE_DOSE"

        elif drug_id == "metformin":
            if egfr < 30 or aki or crcl < 30:
                status = "CONTRAINDICATED"
                severity_score = 95
                recommended_regimen = "HOLD / DISCONTINUE IMMEDIATELY"
                reason = f"eGFR is {egfr:.1f} mL/min/1.73m2 (<30 threshold)" if egfr < 30 else f"Acute Kidney Injury ({kinetics['aki_stage']}, keGFR {kinetics['kegfr_ml_min']} mL/min)"
                clinical_rationale = f"Contraindicated due to {reason}. High risk of Metformin-Associated Lactic Acidosis (MALA)."
                action_type = "HOLD_OR_SWITCH"
            elif egfr < 45:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 75
                recommended_regimen = "Max 500 mg PO BID (Do not initiate new therapy; halve existing dose)"
                clinical_rationale = f"eGFR is {egfr:.1f} mL/min/1.73m2 (30-44 G3b window per FDA label). Limit to <=1000 mg/day."
                action_type = "REDUCE_DOSE"

        elif drug_id == "sitagliptin":
            if egfr < 30 or crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = "25 mg PO daily (75% dose reduction)"
                clinical_rationale = f"eGFR is {egfr:.1f} mL/min/1.73m2 (<30 threshold). Reduce from 100 mg to 25 mg daily."
                action_type = "REDUCE_DOSE"
            elif egfr < 45 or crcl < 45:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 60
                recommended_regimen = "50 mg PO daily (50% dose reduction)"
                clinical_rationale = f"eGFR is {egfr:.1f} mL/min/1.73m2 (30-44 threshold). Reduce from 100 mg to 50 mg daily."
                action_type = "REDUCE_DOSE"

        elif drug_id == "gabapentin":
            if crcl < 15:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 85
                recommended_regimen = "100-300 mg PO q24h (Max 300 mg/day)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<15 mL/min). Elimination half-life extends from 6.5h to 52h."
                action_type = "REDUCE_DOSE"
            elif crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "200-700 mg PO q24h (Max 700 mg/day)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-29 mL/min window). Reduce total daily dose to 200-700 mg once daily."
                action_type = "REDUCE_DOSE"
            elif crcl < 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 65
                recommended_regimen = "200-700 mg PO BID (400-1400 mg/day max)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-59 mL/min window). Cap total daily dose at <=1400 mg divided BID."
                action_type = "REDUCE_DOSE"

        elif drug_id == "pregabalin":
            if crcl < 15:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "25-75 mg PO q24h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<15 mL/min). Reduce to once-daily 25-75 mg."
                action_type = "REDUCE_DOSE"
            elif crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 75
                recommended_regimen = "25-150 mg PO q24h (or divided BID)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-29 mL/min). Reduce daily dose by 75%."
                action_type = "REDUCE_DOSE"
            elif crcl < 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 60
                recommended_regimen = "75-150 mg PO BID (Max 300 mg/day)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-59 mL/min). Reduce daily dose by 50%."
                action_type = "REDUCE_DOSE"

        elif drug_id == "vancomycin":
            # Bug 7 Fix: Cap Vancomycin single dose at 2000 mg to prevent obesity overdosing
            vanc_dose = min(2000, int(round(wt * 15 / 250.0) * 250))
            if crcl < 15 or aki:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 90
                recommended_regimen = f"Load 15-20 mg/kg ({vanc_dose} mg, max 2000 mg) IV x1, then redose by serum level / AUC"
                clinical_rationale = (
                    f"Effective CrCl is {crcl:.1f} mL/min (or active AKI: {kinetics['aki_stage']}). "
                    f"Hold scheduled maintenance until serum trough/AUC24 is verified."
                )
                action_type = "TDM_HOLD"
            elif crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = f"15 mg/kg ({vanc_dose} mg) IV q48h (verify AUC/trough before 2nd dose)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-29 mL/min). Extend interval to q48h with TDM."
                action_type = "REDUCE_DOSE"
            elif crcl < 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = f"15 mg/kg ({vanc_dose} mg) IV q24h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-49 mL/min). Extend dosing interval from q12h to q24h."
                action_type = "REDUCE_DOSE"

        elif drug_id == "cefepime":
            if crcl <= 10:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 90
                recommended_regimen = "1 g IV q24h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<=10). High risk of non-convulsive status epilepticus / neurotoxicity."
                action_type = "REDUCE_DOSE"
            elif crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 85
                recommended_regimen = "2 g IV q24h (or 1 g IV q12h)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (11-29 mL/min). Reduce from q8h to q24h to prevent neurotoxicity."
                action_type = "REDUCE_DOSE"
            elif crcl <= 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = "2 g IV q12h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-60 mL/min). Extend interval from q8h to q12h."
                action_type = "REDUCE_DOSE"

        elif drug_id == "meropenem":
            if crcl < 10:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "500 mg IV q24h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<10 mL/min). Reduce to 500 mg IV q24h."
                action_type = "REDUCE_DOSE"
            elif crcl <= 25:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 75
                recommended_regimen = "500 mg IV q12h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (10-25 mL/min). Reduce dose by 50% and extend to q12h."
                action_type = "REDUCE_DOSE"
            elif crcl <= 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 65
                recommended_regimen = "1 g IV q12h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (26-50 mL/min). Extend interval from q8h to q12h."
                action_type = "REDUCE_DOSE"

        elif drug_id == "piperacillin_tazobactam":
            if crcl < 20:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "2.25 g IV q8h (or 2.25 g IV q6h for nosocomial pneumonia)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<20 mL/min). Reduce dose and extend interval."
                action_type = "REDUCE_DOSE"
            elif crcl <= 40:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = "2.25 g IV q6h (or 3.375 g IV q6h for nosocomial pneumonia)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (20-40 mL/min). Reduce from 4.5 g q6h to 2.25-3.375 g q6h."
                action_type = "REDUCE_DOSE"

        elif drug_id == "ciprofloxacin":
            if crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 75
                recommended_regimen = "250-500 mg PO q18-24h (or 400 mg IV q24h)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<30 mL/min). Extend interval to q18-24h."
                action_type = "REDUCE_DOSE"
            elif crcl <= 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 60
                recommended_regimen = "250-500 mg PO q12h (or 400 mg IV q12h)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-50 mL/min). Avoid high-dose q8h IV regimen."
                action_type = "REDUCE_DOSE"

        elif drug_id == "levofloxacin":
            if crcl < 20:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "750 mg x1 load, then 500 mg PO/IV q48h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<20 mL/min). Substantially prolonged renal elimination."
                action_type = "REDUCE_DOSE"
            elif crcl < 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = "750 mg PO/IV q48h (or 500 mg x1, then 250 mg q24h)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (20-49 mL/min). Extend 750 mg interval to q48h."
                action_type = "REDUCE_DOSE"

        elif drug_id == "tmp_smx":
            if crcl < 15 or k_val >= 5.5:
                status = "CONTRAINDICATED"
                severity_score = 92
                recommended_regimen = "AVOID / Discontinue (Switch to non-hyperkalemic alternative)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min and/or Serum K+ is {k_val:.1f} mEq/L. Trimethoprim blocks ENaC channels, causing severe hyperkalemia."
                action_type = "HOLD_OR_SWITCH"
            elif crcl <= 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 78
                recommended_regimen = "1 DS tablet PO q24h (or 1 SS tablet PO q12h — 50% reduction)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-30 mL/min). Reduce total daily dose by 50% and monitor K+ closely."
                action_type = "REDUCE_DOSE"

        elif drug_id == "acyclovir":
            if crcl < 10:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 88
                recommended_regimen = f"2.5-5 mg/kg ({round(adj_wt * 3.5):.0f} mg) IV q24h + IV hydration"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<10 mL/min). High risk of intratubular crystal nephropathy and neurotoxicity."
                action_type = "REDUCE_DOSE"
            elif crcl < 25:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = f"5-10 mg/kg ({round(adj_wt * 5):.0f} mg) IV q24h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (10-24 mL/min). Extend interval from q8h to q24h."
                action_type = "REDUCE_DOSE"
            elif crcl <= 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = f"5-10 mg/kg ({round(adj_wt * 5):.0f} mg) IV q12h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (25-50 mL/min). Extend interval from q8h to q12h."
                action_type = "REDUCE_DOSE"

        elif drug_id in ("lisinopril", "losartan"):
            if aki or k_val >= 5.5:
                status = "CONTRAINDICATED"
                severity_score = 92
                recommended_regimen = "HOLD DURING ACUTE KIDNEY INJURY / HYPERKALEMIA"
                clinical_rationale = f"Active {kinetics['aki_stage']} or Hyperkalemia (K+ {k_val:.1f} mEq/L). RAAS blockade dilates efferent arteriole and worsens AKI/hyperkalemia."
                action_type = "HOLD_OR_SWITCH"
            elif crcl <= 30 and drug_id == "lisinopril":
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 65
                recommended_regimen = "Initial 2.5-5 mg PO daily (Monitor SCr and K+ within 72h)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<=30 mL/min). Lisinopril is renally excreted unchanged."
                action_type = "REDUCE_DOSE"

        elif drug_id == "spironolactone":
            if crcl < 30 or k_val > 5.0 or aki:
                status = "CONTRAINDICATED"
                severity_score = 95
                recommended_regimen = "CONTRAINDICATED / HOLD IMMEDIATELY"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<30) or K+ is {k_val:.1f} mEq/L (>5.0) or active AKI. High risk of fatal hyperkalemic arrhythmia."
                action_type = "HOLD_OR_SWITCH"
            elif crcl < 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 75
                recommended_regimen = "12.5-25 mg PO daily or q48h (Recheck K+ in 3-5 days)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-49 mL/min). Reduce dose and monitor serum potassium closely."
                action_type = "REDUCE_DOSE"

        elif drug_id == "furosemide":
            if aki:
                status = "MONITOR_CLOSELY"
                severity_score = 60
                recommended_regimen = "Assess volume status: Hold if hypovolemic/pre-renal AKI; continue only for hypervolemic congestion"
                clinical_rationale = f"Patient has {kinetics['aki_stage']}. Loop diuretics exacerbate pre-renal AKI and trigger Triple Whammy if paired with RAASi/NSAID."
                action_type = "MONITOR"

        elif drug_id in ("ibuprofen", "ketorolac"):
            if crcl < 30 or aki:
                status = "CONTRAINDICATED"
                severity_score = 98
                recommended_regimen = "DISCONTINUE IMMEDIATELY (Switch to Acetaminophen / topical / non-NSAID)"
                clinical_rationale = f"Contraindicated in CrCl <30 mL/min ({crcl:.1f} mL/min) or active AKI ({kinetics['aki_stage']}). Causes afferent arteriolar vasoconstriction."
                action_type = "HOLD_OR_SWITCH"
            elif crcl < 60 or (drug_id == "ketorolac" and (age >= 65 or wt < 50)):
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 85
                recommended_regimen = (
                    "Avoid if possible; otherwise max 15 mg IV q6h (50% reduction) for <=5 days"
                    if drug_id == "ketorolac"
                    else "Avoid routine use in CKD G3; if essential, lowest dose for <=3-5 days with SCr check"
                )
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<60) or Age >=65 ({age:.0f}y). High risk of NSAID nephrotoxicity."
                action_type = "REDUCE_DOSE"

        elif drug_id == "allopurinol":
            if crcl < 15:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 80
                recommended_regimen = "50 mg PO q48-72h (Max 100 mg/day only with specialist titration)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<15). Oxipurinol metabolite accumulates (t1/2 ~70h), increasing DRESS/SJS risk."
                action_type = "REDUCE_DOSE"
            elif crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 72
                recommended_regimen = "50-100 mg PO daily"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (15-29 mL/min). Reduce starting/maintenance dose to 50-100 mg daily."
                action_type = "REDUCE_DOSE"
            elif crcl < 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 55
                recommended_regimen = "100-200 mg PO daily"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-59 mL/min). Avoid unadjusted >=300 mg initial dosing."
                action_type = "REDUCE_DOSE"

        elif drug_id == "morphine":
            if crcl < 30:
                status = "CONTRAINDICATED"
                severity_score = 90
                recommended_regimen = "AVOID / Switch to Fentanyl or Hydromorphone (low dose)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<30 mL/min). Active M6G and M3G glucuronide metabolites accumulate, causing delayed coma."
                action_type = "HOLD_OR_SWITCH"
            elif crcl < 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = "Reduce dose by 25-50% and extend interval, or switch to Hydromorphone/Fentanyl"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-59 mL/min). M6G metabolite clearance is reduced."
                action_type = "REDUCE_DOSE"

        elif drug_id in ("gentamicin", "amikacin"):
            mg_kg = 5 if drug_id == "gentamicin" else 15
            calc_dose = int(round(adj_wt * mg_kg / 10.0) * 10)
            if crcl < 20 or aki:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 92
                recommended_regimen = f"Load {calc_dose} mg ({mg_kg} mg/kg AdjBW) IV x1, then redose strictly by serum TDM levels"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (or {kinetics['aki_stage']}). High risk of irreversible ototoxicity and acute tubular necrosis."
                action_type = "TDM_HOLD"
            elif crcl < 40:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 82
                recommended_regimen = f"{calc_dose} mg ({mg_kg} mg/kg AdjBW) IV q48h (Verify trough <1 mcg/mL before 2nd dose)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (20-39 mL/min). Extend interval from q24h to q48h."
                action_type = "REDUCE_DOSE"
            elif crcl < 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 70
                recommended_regimen = f"{calc_dose} mg ({mg_kg} mg/kg AdjBW) IV q36h with therapeutic drug monitoring"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (40-59 mL/min). Extend interval to q36h."
                action_type = "REDUCE_DOSE"

        elif drug_id == "colchicine":
            if crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 88
                recommended_regimen = "Prophylaxis: 0.3 mg PO daily or q48h; Acute flare: 0.6 mg x1 (Do not repeat for 14 days)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<30 mL/min). Severe risk of colchicine myoneuropathy, rhabdomyolysis, and pancytopenia."
                action_type = "REDUCE_DOSE"
            elif crcl < 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 68
                recommended_regimen = "Prophylaxis: 0.6 mg PO once daily (Monitor for GI toxicity/myopathy)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-49 mL/min). Reduce maintenance prophylaxis to once daily."
                action_type = "REDUCE_DOSE"

        elif drug_id == "fluconazole":
            if crcl <= 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 72
                recommended_regimen = "Load 400 mg x1, then reduce maintenance by 50% (100-200 mg PO/IV q24h)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<=50 mL/min). Fluconazole is 80% renally excreted unchanged; halve maintenance dose."
                action_type = "REDUCE_DOSE"

        elif drug_id == "digoxin":
            if crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 88
                recommended_regimen = "0.0625 mg PO q48h (Target serum digoxin 0.5-0.9 ng/mL; reduce load by 50%)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<30 mL/min). Volume of distribution and renal clearance are markedly reduced; high arrhythmia risk."
                action_type = "REDUCE_DOSE"
            elif crcl < 60:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 72
                recommended_regimen = "0.0625-0.125 mg PO once daily (Check trough in 5-7 days)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-59 mL/min). Narrow therapeutic index."
                action_type = "REDUCE_DOSE"

        elif drug_id == "famotidine":
            if crcl < 30:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 68
                recommended_regimen = "20 mg PO/IV q24h (or 20 mg q48h — 50% reduction)"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (<30 mL/min). Unadjusted famotidine causes CNS accumulation, delirium, and agitation in elderly/CKD patients."
                action_type = "REDUCE_DOSE"
            elif crcl < 50:
                status = "DOSE_REDUCTION_REQUIRED"
                severity_score = 55
                recommended_regimen = "20 mg PO/IV q24h"
                clinical_rationale = f"Effective CrCl is {crcl:.1f} mL/min (30-49 mL/min). Reduce from BID to once daily."
                action_type = "REDUCE_DOSE"

    # Bug 3 Fix: Unified reconciliation state detection between Python backend and Browser UI
    norm_curr = str(current_dose or "").strip().lower()
    norm_rec = str(recommended_regimen).strip().lower()
    if status != "OPTIMAL" and norm_curr and norm_curr == norm_rec:
        status = "OPTIMAL"
        severity_score = 0
        action_type = "RECONCILED"
        clinical_rationale = "Dose has been reconciled to match renal pharmacokinetic guidance."

    renal_fraction = max(0.0, min(1.0, (90.0 - min(crcl, 90.0)) / 80.0))
    est_half_life_h = info["half_life_normal_h"] + renal_fraction * (
        info["half_life_esrd_h"] - info["half_life_normal_h"]
    )

    return {
        "drug_id": drug_id,
        "name": info["name"],
        "category": info["category"],
        "therapeutic_class": info["therapeutic_class"],
        "index_metric": info["index_metric"],
        "current_dose": current_dose or info["standard_dose"],
        "recommended_regimen": recommended_regimen,
        "status": status,
        "severity_score": severity_score,
        "action_type": action_type,
        "clinical_rationale": clinical_rationale,
        "est_half_life_h": round(est_half_life_h, 1),
        "normal_half_life_h": info["half_life_normal_h"],
        "sick_day_hold": info.get("sick_day_hold", False),
        "source_title": info["source_title"],
        "source_url": info["source_url"],
    }


def detect_multi_drug_syndromes(
    regimen_items: List[Dict[str, str]],
    kinetics: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Detects 7 multi-drug nephrotoxic, hemodynamic, electrolyte, bleeding, QTc, and duplication
    syndromes across active medication orders (excluding orders already marked HOLD/DISCONTINUE/AVOID).
    """
    active_ids = [
        item["drug_id"]
        for item in regimen_items
        if item.get("drug_id") in FORMULARY
        and not str(item.get("current_dose", "")).strip().upper().startswith(("HOLD", "DISCONTINUE", "AVOID", "CONTRAINDICATED"))
    ]
    drugs = [FORMULARY[d] for d in active_ids]
    syndromes: List[Dict[str, Any]] = []

    raas_drugs = [d["name"] for d in drugs if d["therapeutic_class"] == "raas_inhibitor"]
    diuretic_drugs = [
        d["name"] for d in drugs if d["therapeutic_class"] in ("diuretic", "k_sparing_diuretic")
    ]
    nsaid_drugs = [d["name"] for d in drugs if d["therapeutic_class"] == "nsaid"]

    # 1. Triple Whammy Hemodynamic AKI
    if raas_drugs and diuretic_drugs and nsaid_drugs:
        syndromes.append({
            "syndrome_id": "triple_whammy",
            "title": "CRITICAL: 'Triple Whammy' Hemodynamic Acute Kidney Injury Triad",
            "severity": "CRITICAL",
            "involved_drugs": raas_drugs + diuretic_drugs + nsaid_drugs,
            "mechanism": (
                "Simultaneous efferent arteriolar vasodilation (ACEi/ARB: "
                f"{', '.join(raas_drugs)}), plasma volume depletion (Diuretic: "
                f"{', '.join(diuretic_drugs)}), and COX-mediated afferent arteriolar "
                f"vasoconstriction (NSAID: {', '.join(nsaid_drugs)}) collapses glomerular hydrostatic pressure."
            ),
            "management": (
                "Immediately discontinue NSAID, hold RAAS inhibitor and reassess diuretic volume status; "
                "recheck Basic Metabolic Panel (SCr, K+, BUN) within 24 hours."
            ),
            "source_title": "Mechanisms of Triple Whammy Acute Kidney Injury (bpac.org.nz / PMC9889944)",
            "source_url": "https://bpac.org.nz/2018/triple-whammy.aspx",
        })
    elif (raas_drugs and nsaid_drugs) or (diuretic_drugs and nsaid_drugs):
        paired = (raas_drugs or diuretic_drugs) + nsaid_drugs
        syndromes.append({
            "syndrome_id": "dual_hemodynamic_nephrotoxicity",
            "title": "HIGH RISK: Dual Hemodynamic Renal Insult (NSAID + RAASi/Diuretic)",
            "severity": "HIGH",
            "involved_drugs": paired,
            "mechanism": (
                "NSAID afferent vasoconstriction blunts compensatory renal autoregulation in the presence of "
                f"{', '.join(raas_drugs or diuretic_drugs)}."
            ),
            "management": "Discontinue NSAID and substitute non-nephrotoxic analgesia; monitor SCr and blood pressure.",
            "source_title": "NSAID-Induced AKI Risk in Patients on RAASi (PMC12359997)",
            "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC12359997/",
        })

    # 2. Synergistic Vancomycin + Piperacillin-Tazobactam OR Aminoglycoside Tubulointerstitial Nephrotoxicity
    aminoglycosides = [d["name"] for d in drugs if d["therapeutic_class"] == "aminoglycoside"]
    if "vancomycin" in active_ids and ("piperacillin_tazobactam" in active_ids or aminoglycosides):
        partners = (
            [FORMULARY["piperacillin_tazobactam"]["name"]] if "piperacillin_tazobactam" in active_ids else []
        ) + aminoglycosides
        syndromes.append({
            "syndrome_id": "vanc_synergistic_aki",
            "title": "HIGH RISK: Vancomycin + Beta-Lactam/Aminoglycoside Synergistic Nephrotoxicity",
            "severity": "HIGH",
            "involved_drugs": [FORMULARY["vancomycin"]["name"]] + partners,
            "mechanism": (
                "Concomitant Vancomycin with Piperacillin-Tazobactam or Aminoglycosides increases acute tubular necrosis "
                "and AKI incidence 2- to 3-fold via proximal tubular oxidative stress."
            ),
            "management": (
                "Consider switching Piperacillin-Tazobactam to Cefepime or Meropenem (renally adjusted), "
                "avoid concurrent aminoglycosides if alternatives exist, and monitor Vancomycin AUC24/MIC + daily SCr."
            ),
            "source_title": "IDSA / Nebraska Medicine Antimicrobial Stewardship Renal Protocol",
            "source_url": "https://www.nebraskamed.com/sites/default/files/documents/for-providers/asp/tnmc-anti-infective-renal-dosing-guidelines.pdf",
        })

    # 3. Hyperkalemic Cascade
    hyperk_drugs = [d["name"] for d in drugs if d["hyperkalemic"]]
    if len(hyperk_drugs) >= 2 and (kinetics["effective_dosing_crcl"] < 50 or kinetics["potassium_meq_l"] >= 4.8):
        sev = "CRITICAL" if (len(hyperk_drugs) >= 3 or kinetics["potassium_meq_l"] >= 5.2) else "HIGH"
        syndromes.append({
            "syndrome_id": "hyperkalemic_cascade",
            "title": f"{sev}: Multi-Drug Hyperkalemic Cascade in Reduced Renal Clearance",
            "severity": sev,
            "involved_drugs": hyperk_drugs,
            "mechanism": (
                f"Concurrent potassium-retaining agents ({', '.join(hyperk_drugs)}) in a patient with "
                f"effective CrCl {kinetics['effective_dosing_crcl']:.1f} mL/min and serum K+ {kinetics['potassium_meq_l']:.1f} mEq/L "
                "synergistically impair aldosterone-mediated distal tubular potassium excretion."
            ),
            "management": (
                "Hold potassium-sparing diuretics (Spironolactone) and trimethoprim/NSAIDs; obtain stat BMP/ECG if K+ >=5.5 mEq/L."
            ),
            "source_title": "RACGP Prescribing in Chronic Renal Impairment & Hyperkalemia",
            "source_url": "https://www.racgp.org.au/afp/2013/january-february/prescribing-for-older-people-with-cri",
        })

    # 4. Therapeutic Duplication (DDInter 2.0 Classification)
    class_groups: Dict[str, List[str]] = {}
    for d in drugs:
        tc = d["therapeutic_class"]
        class_groups.setdefault(tc, []).append(d["name"])
    for tc, names in class_groups.items():
        if len(names) >= 2:
            syndromes.append({
                "syndrome_id": f"duplication_{tc}",
                "title": f"CRITICAL: Therapeutic Class Duplication ({tc.replace('_', ' ').title()})",
                "severity": "CRITICAL",
                "involved_drugs": names,
                "mechanism": (
                    f"Concurrent prescription of multiple {tc.replace('_', ' ')} agents ({', '.join(names)}) "
                    "compounds dose-dependent toxicity without additive therapeutic efficacy."
                ),
                "management": f"Reconcile medication list and discontinue duplicate {tc.replace('_', ' ')} order immediately.",
                "source_title": "DDInter 2.0: Therapeutic Duplication & DDI Resource (PMC11701621)",
                "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11701621/",
            })

    # 5. Anticoagulant + NSAID / Multi-Bleed Matrix
    anticoags = [d["name"] for d in drugs if d["therapeutic_class"] == "anticoagulant"]
    if anticoags and nsaid_drugs:
        syndromes.append({
            "syndrome_id": "anticoag_nsaid_bleed",
            "title": "CRITICAL: Anticoagulant + NSAID Hemorrhagic Synergy in Renal Impairment",
            "severity": "CRITICAL",
            "involved_drugs": anticoags + nsaid_drugs,
            "mechanism": (
                f"Combining systemic anticoagulation ({', '.join(anticoags)}) with COX-1/2 platelet inhibition and gastric mucosal erosion "
                f"({', '.join(nsaid_drugs)}) in reduced renal clearance markedly elevates major GI and retroperitoneal bleed risk."
            ),
            "management": "Discontinue NSAID immediately; check hemoglobin/hematocrit and ensure anticoagulant is renally dose-adjusted.",
            "source_title": "DDInter 2.0 Drug Interaction Database (PMC11701621)",
            "source_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11701621/",
        })

    # 6. Multi-Drug QTc Prolongation Synergy in Renal Accumulation (New in v3.0)
    qt_drugs = [d["name"] for d in drugs if d["qt_prolonging"]]
    if len(qt_drugs) >= 2 and kinetics["effective_dosing_crcl"] < 50:
        syndromes.append({
            "syndrome_id": "qtc_renal_synergy",
            "title": "HIGH RISK: Renally Accumulated QTc-Prolonging Synergy (Torsades de Pointes Risk)",
            "severity": "HIGH",
            "involved_drugs": qt_drugs,
            "mechanism": (
                f"Impaired renal elimination (effective CrCl {kinetics['effective_dosing_crcl']:.1f} mL/min) elevates plasma concentrations "
                f"of multiple hERG-blocking QTc-prolonging agents ({', '.join(qt_drugs)})."
            ),
            "management": "Obtain baseline and follow-up 12-lead ECG (monitor QTc <500 ms), correct K+ >4.0 mEq/L and Mg2+ >2.0 mg/dL, and adjust doses for CrCl.",
            "source_title": "Rhode Island APRN Prescribing Pharmacology QTc & Renal Bundle",
            "source_url": "https://nursingcecentral.com/lessons/rhode-island-aprn-prescribing-renewal-pharmacology-bundle/",
        })

    return syndromes


def generate_patient_counseling_handout(
    patient_meta: Dict[str, Any],
    kinetics: Dict[str, Any],
    drug_evaluations: List[Dict[str, Any]],
) -> Dict[str, str]:
    """
    Generates a plain-language, health-equity focused Patient Kidney Safety & 'Sick Day Rules'
    Handout in English, Hindi (हिन्दी), and Kannada (ಕನ್ನಡ).
    """
    name = patient_meta.get("name", "Patient")
    sick_day_meds = [d["name"] for d in drug_evaluations if d.get("sick_day_hold")]
    adjusted_meds = [
        f"{d['name']} -> {d['recommended_regimen']}"
        for d in drug_evaluations
        if d["status"] in ("CONTRAINDICATED", "DOSE_REDUCTION_REQUIRED")
    ]
    sick_list_str = ", ".join(sick_day_meds) if sick_day_meds else "blood pressure pills (ACEi/ARB), water pills (diuretics), and Metformin"
    adj_list_str = "; ".join(adjusted_meds) if adjusted_meds else "All current medicines are matched to your kidney function."

    en_text = (
        f"PATIENT KIDNEY SAFETY & SICK-DAY ACTION PLAN — {name}\n"
        f"Kidney Function Summary: Stage {kinetics['kdigo_stage']} (Estimated Dosing Clearance: {kinetics['effective_dosing_crcl']} mL/min)\n\n"
        f"1. MEDICATION CHANGES MADE FOR YOUR SAFETY:\n"
        f"   {adj_list_str}\n\n"
        f"2. CRITICAL 'SICK DAY RULES' (WHEN TO PAUSE MEDICINES):\n"
        f"   If you develop vomiting, diarrhea, high fever, or cannot keep fluids down for more than 24 hours, temporarily PAUSE: {sick_list_str}. Contact your doctor or clinic immediately.\n\n"
        f"3. AVOID OVER-THE-COUNTER KIDNEY HARMS:\n"
        f"   Do NOT take painkillers like Ibuprofen, Diclofenac, Naproxen, Aceclofenac, or Ketorolac without kidney team approval. Use Paracetamol (Acetaminophen) safely as directed."
    )

    hi_text = (
        f"रोगी किडनी सुरक्षा और 'सिक-डे' (बीमारी के दिन) कार्य योजना — {name}\n"
        f"किडनी कार्य सारांश: चरण {kinetics['kdigo_stage']} (अनुमानित क्लीयरेंस: {kinetics['effective_dosing_crcl']} mL/min)\n\n"
        f"1. आपकी सुरक्षा के लिए दवा की खुराक में बदलाव:\n"
        f"   {adj_list_str}\n\n"
        f"2. महत्वपूर्ण 'सिक-डे नियम' (उल्टी/दस्त/निर्जलीकरण होने पर क्या करें):\n"
        f"   यदि आपको तेज बुखार, उल्टी, दस्त हो या आप तरल पदार्थ न ले पा रहे हों, तो इन दवाओं को अस्थायी रूप से रोकें: {sick_list_str} और तुरंत अपने डॉक्टर से संपर्क करें।\n\n"
        f"3. बिना डॉक्टर की सलाह के दर्द निवारक दवाओं (NSAIDs) से बचें:\n"
        f"   इबुप्रोफेन (Ibuprofen), डाइक्लोफेनाक (Diclofenac), या टोरडोल जैसी दर्द की गोलियां न लें—ये किडनी को गंभीर नुकसान पहुंचा सकती हैं।"
    )

    kn_text = (
        f"ರೋಗಿಯ ಕಿಡ್ನಿ (ಮೂತ್ರಪಿಂಡ) ಸುರಕ್ಷತೆ ಮತ್ತು ತುರ್ತು ಸೂಚನೆಗಳು — {name}\n"
        f"ಕಿಡ್ನಿ ಕಾರ್ಯ ಸ್ಥಿತಿ: ಹಂತ {kinetics['kdigo_stage']} (ಕ್ಲಿಯರೆನ್ಸ್: {kinetics['effective_dosing_crcl']} mL/min)\n\n"
        f"1. ನಿಮ್ಮ ಸುರಕ್ಷತೆಗಾಗಿ ಮಾಡಲಾದ ಔಷಧಿ ಬದಲಾವಣೆಗಳು:\n"
        f"   {adj_list_str}\n\n"
        f"2. 'ಸಿಕ್-ಡೇ ನಿಯಮಗಳು' (ವಾಂತಿ, ಭೇದಿ ಅಥವಾ ನಿರ್ಜಲೀಕರಣವಾದಾಗ):\n"
        f"   ನಿಮಗೆ ತೀವ್ರ ವಾಂತಿ, ಭೇದಿ ಅಥವಾ ಜ್ವರ ಬಂದರೆ ಈ ಮಾತ್ರೆಗಳನ್ನು ತಾತ್ಕಾಲಿಕವಾಗಿ ನಿಲ್ಲಿಸಿ: {sick_list_str} ಮತ್ತು ತಕ್ಷಣ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.\n\n"
        f"3. ನೋವು ನಿವಾರಕ ಮಾತ್ರೆಗಳಿಂದ (NSAIDs) ದೂರವಿರಿ:\n"
        f"   ವೈದ್ಯರ ಸಲಹೆಯಿಲ್ಲದೆ Ibuprofen, Diclofenac ನಂತಹ ನೋವು ನಿವಾರಕ ಮಾತ್ರೆಗಳನ್ನು ತೆಗೆದುಕೊಳ್ಳಬೇಡಿ; ಇವು ಕಿಡ್ನಿಗೆ ಹಾನಿ ಮಾಡುತ್ತವೆ."
    )

    return {"en": en_text, "hi": hi_text, "kn": kn_text}


def export_fhir_r4_bundle(
    patient_meta: Dict[str, Any],
    kinetics: Dict[str, Any],
    drug_evaluations: List[Dict[str, Any]],
    syndromes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Exports a standard HL7 FHIR R4 Collection Bundle containing Patient, Renal Observation
    (LOINC 2160-0 Serum Creatinine, 98979-8 CKD-EPI 2021 eGFR, 33558-8 Cockcroft-Gault CrCl),
    MedicationRequest resources, and DetectedIssue alerts for hospital EHR interoperability.
    """
    pid = str(patient_meta.get("id", "pt-1"))
    entries: List[Dict[str, Any]] = [
        {
            "resource": {
                "resourceType": "Patient",
                "id": pid,
                "name": [{"text": str(patient_meta.get("name", "Patient"))}],
                "gender": str(kinetics["sex"]).lower(),
            }
        },
        {
            "resource": {
                "resourceType": "Observation",
                "id": f"obs-renal-{pid}",
                "status": "final",
                "code": {
                    "coding": [
                        {"system": "http://loinc.org", "code": "2160-0", "display": "Creatinine [Mass/volume] in Serum or Plasma"},
                        {"system": "http://loinc.org", "code": "98979-8", "display": "GFR/1.73 sq M.predicted [Volume Rate/Area] in Serum, Plasma or Blood by Creatinine-based formula (CKD-EPI 2021)"},
                    ]
                },
                "subject": {"reference": f"Patient/{pid}"},
                "component": [
                    {"code": {"text": "Serum Creatinine (mg/dL)"}, "valueQuantity": {"value": kinetics["scr_mg_dl"], "unit": "mg/dL"}},
                    {"code": {"text": "Cockcroft-Gault CrCl (Selected)"}, "valueQuantity": {"value": kinetics["crcl_selected"], "unit": "mL/min"}},
                    {"code": {"text": "Chen Kinetic eGFR (keGFR)"}, "valueQuantity": {"value": kinetics["kegfr_ml_min"], "unit": "mL/min"}},
                    {"code": {"text": "2021 CKD-EPI eGFR (Indexed)"}, "valueQuantity": {"value": kinetics["egfr_indexed"], "unit": "mL/min/1.73m2"}},
                ],
            }
        },
    ]

    for d in drug_evaluations:
        entries.append({
            "resource": {
                "resourceType": "MedicationRequest",
                "id": f"medreq-{pid}-{d['drug_id']}",
                "status": "stopped" if d["status"] == "CONTRAINDICATED" else "active",
                "intent": "order",
                "medicationCodeableConcept": {"text": d["name"]},
                "subject": {"reference": f"Patient/{pid}"},
                "dosageInstruction": [
                    {
                        "text": f"Ordered: {d['current_dose']} | Recommended: {d['recommended_regimen']}",
                        "patientInstruction": d["clinical_rationale"],
                    }
                ],
            }
        })

    for s in syndromes:
        entries.append({
            "resource": {
                "resourceType": "DetectedIssue",
                "id": f"issue-{pid}-{s['syndrome_id']}",
                "status": "final",
                "severity": "high" if s["severity"] in ("CRITICAL", "HIGH") else "moderate",
                "code": {"text": s["title"]},
                "patient": {"reference": f"Patient/{pid}"},
                "detail": f"{s['mechanism']} Management: {s['management']}",
            }
        })

    return {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "entry": entries,
    }


def generate_ipass_handoff(
    patient_meta: Dict[str, Any],
    kinetics: Dict[str, Any],
    drug_evaluations: List[Dict[str, Any]],
    syndromes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generates a structured 5-part I-PASS clinical handoff block grounded in the patient's
    verified renal audit, including Chen keGFR and RRT status.
    """
    critical_drugs = [d for d in drug_evaluations if d["status"] in ("CONTRAINDICATED", "DOSE_REDUCTION_REQUIRED")]
    critical_syndromes = [s for s in syndromes if s["severity"] in ("CRITICAL", "HIGH")]

    if any(d["status"] == "CONTRAINDICATED" for d in drug_evaluations) or any(
        s["severity"] == "CRITICAL" for s in syndromes
    ) or kinetics["aki_detected"]:
        illness_severity = "WATCHER / HIGH-RISK RENAL ALERT"
    elif critical_drugs or critical_syndromes:
        illness_severity = "MODERATE — DOSE ADJUSTMENT PENDING"
    else:
        illness_severity = "STABLE — RENALLY RECONCILED"

    name = patient_meta.get("name", "Unidentified Patient")
    room = patient_meta.get("room", "Ward Bed")
    dx = patient_meta.get("primary_diagnosis", "Inpatient Medical Care")
    rrt_tag = f" | RRT: {kinetics['rrt_modality'].upper()}" if kinetics.get("rrt_modality", "none") != "none" else ""
    cys_tag = (
        f" | 2021 CKD-EPI Cr-Cys Combined: {kinetics['egfr_cr_cys_indexed']} mL/min/1.73m2"
        if kinetics.get("egfr_cr_cys_indexed") is not None
        else ""
    )

    div_note = (
        f" [KINETICS: CG CrCl {kinetics['crcl_selected']} mL/min ({kinetics['selected_weight_basis']} {kinetics['selected_weight_kg']} kg) | "
        f"Chen Kinetic eGFR (keGFR) {kinetics['kegfr_ml_min']} mL/min | "
        f"Lab 2021 CKD-EPI Indexed {kinetics['egfr_indexed']} mL/min/1.73m2 | "
        f"BSA De-Indexed {kinetics['egfr_non_indexed']} mL/min{cys_tag}{rrt_tag}]"
    )

    patient_summary = (
        f"{name} ({kinetics['age']:.0f}yo {kinetics['sex']}, {kinetics['weight_kg']} kg, {kinetics['height_cm']} cm, "
        f"BMI {kinetics['bmi']} kg/m2, {room}) admitted for {dx}. "
        f"Current SCr {kinetics['scr_mg_dl']:.2f} mg/dL "
        f"(Baseline: {kinetics['baseline_scr_mg_dl'] or 'N/A'} mg/dL over {kinetics['delta_hours']:.0f}h; {kinetics['aki_stage']}), "
        f"K+ {kinetics['potassium_meq_l']:.1f} mEq/L, KDIGO Stage {kinetics['kdigo_stage']}."
        + div_note
    )

    action_items: List[str] = []
    for s in critical_syndromes:
        action_items.append(f"[SYNDROME - {s['severity']}] {s['title']}: {s['management']}")
    for d in critical_drugs:
        action_items.append(
            f"[{d['action_type']}] {d['name']}: Change from '{d['current_dose']}' -> '{d['recommended_regimen']}' ({d['clinical_rationale']})"
        )
    if not action_items:
        action_items.append("All active medications are appropriately dosed for current renal clearance; continue routine BMP monitoring.")

    contingency_items: List[str] = [
        f"Recheck Basic Metabolic Panel (SCr, BUN, K+, HCO3-) in {'12-24 hours' if kinetics['aki_detected'] or critical_syndromes else '24-48 hours'}.",
    ]
    if kinetics["potassium_meq_l"] >= 5.0 or any(s["syndrome_id"] == "hyperkalemic_cascade" for s in syndromes):
        contingency_items.append(
            "If repeat serum K+ >=5.5 mEq/L or ECG shows peaked T-waves, initiate hyperkalemia protocol and verify all RAASi/K+-sparing agents remain held."
        )
    if any(d["drug_id"] in ("vancomycin", "gentamicin", "amikacin") for d in drug_evaluations):
        contingency_items.append(
            "Verify Vancomycin/Aminoglycoside serum trough or AUC24 level prior to administering next maintenance dose."
        )
    if any(d["therapeutic_class"] == "anticoagulant" for d in drug_evaluations):
        contingency_items.append(
            "Monitor hemoglobin/hematocrit and signs of overt or occult bleeding given renally cleared anticoagulation."
        )

    synthesis_prompt = (
        f"Incoming clinician confirms receipt of {len(action_items)} medication reconciliation action(s), "
        f"acknowledges effective dosing clearance ({kinetics['effective_dosing_crcl']} mL/min), "
        f"and confirms follow-up BMP timing."
    )

    markdown_text = (
        f"### I-PASS CLINICAL SHIFT HANDOFF — {name} ({room})\n"
        f"- **I — Illness Severity**: **{illness_severity}**\n"
        f"- **P — Patient Summary**: {patient_summary}\n"
        f"- **A — Action List (Medication & Renal Reconciliation)**:\n"
        + "\n".join(f"  - {item}" for item in action_items)
        + "\n"
        f"- **S — Situation Awareness & Contingency Planning**:\n"
        + "\n".join(f"  - {item}" for item in contingency_items)
        + "\n"
        f"- **S — Synthesis by Receiver**: {synthesis_prompt}\n"
    )

    return {
        "illness_severity": illness_severity,
        "patient_summary": patient_summary,
        "action_list": action_items,
        "contingency_planning": contingency_items,
        "synthesis_by_receiver": synthesis_prompt,
        "markdown": markdown_text,
    }


def evaluate_full_patient_case(case_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    End-to-end v3.0 evaluation pipeline taking a patient case dictionary and returning
    kinetics, per-drug evaluations, multi-drug syndromes, safety score, I-PASS handoff,
    multilingual patient counseling handout, and HL7 FHIR R4 bundle.
    """
    kinetics = compute_renal_kinetics(
        age=float(case_payload["age"]),
        sex=str(case_payload["sex"]),
        weight_kg=float(case_payload["weight_kg"]),
        height_cm=float(case_payload["height_cm"]),
        scr_value=float(case_payload["scr_value"]),
        scr_unit=str(case_payload.get("scr_unit", "mg_dl")),
        baseline_scr_mg_dl=(
            float(case_payload["baseline_scr_mg_dl"])
            if case_payload.get("baseline_scr_mg_dl") not in (None, "")
            else None
        ),
        potassium_meq_l=float(case_payload.get("potassium_meq_l", 4.2)),
        weight_override=str(case_payload.get("weight_override", "auto")),
        delta_hours=float(case_payload.get("delta_hours", 24.0) or 24.0),
        cystatin_c_mg_l=(
            float(case_payload["cystatin_c_mg_l"])
            if case_payload.get("cystatin_c_mg_l") not in (None, "")
            else None
        ),
        rrt_modality=str(case_payload.get("rrt_modality", "none") or "none"),
        crrt_effluent_ml_kg_h=float(case_payload.get("crrt_effluent_ml_kg_h", 25.0) or 25.0),
    )

    regimen = case_payload.get("medications", [])
    drug_evals = [
        evaluate_drug_for_patient(item["drug_id"], item.get("current_dose", ""), kinetics)
        for item in regimen
        if item.get("drug_id") in FORMULARY
    ]
    syndromes = detect_multi_drug_syndromes(regimen, kinetics)
    ipass = generate_ipass_handoff(case_payload, kinetics, drug_evals, syndromes)
    handout = generate_patient_counseling_handout(case_payload, kinetics, drug_evals)
    fhir_bundle = export_fhir_r4_bundle(case_payload, kinetics, drug_evals, syndromes)

    penalty = 0
    for d in drug_evals:
        if d["status"] == "CONTRAINDICATED":
            penalty += 28
        elif d["status"] == "DOSE_REDUCTION_REQUIRED":
            penalty += 16
        elif d["status"] == "MONITOR_CLOSELY":
            penalty += 6
    for s in syndromes:
        penalty += 25 if s["severity"] == "CRITICAL" else 15
    if kinetics["aki_detected"]:
        penalty += 10
    safety_score = max(0, 100 - penalty)

    return {
        "patient": {
            "id": html.escape(str(case_payload.get("id", "custom"))),
            "name": html.escape(str(case_payload.get("name", "Patient"))),
            "room": html.escape(str(case_payload.get("room", "Ward"))),
            "primary_diagnosis": html.escape(str(case_payload.get("primary_diagnosis", "General Inpatient"))),
        },
        "kinetics": kinetics,
        "drug_evaluations": drug_evals,
        "syndromes": syndromes,
        "safety_score": safety_score,
        "ipass": ipass,
        "patient_handout": handout,
        "fhir_bundle": fhir_bundle,
    }
