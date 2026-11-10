"""Validate case structure at the HTTP boundary before evaluation or storage."""
import math

from engine import FORMULARY


def validate_case(case):
    if not isinstance(case, dict):
        raise ValueError("Send a JSON object for a case.")
    case = dict(case)
    required = ("age", "weight_kg", "height_cm", "scr_value")
    optional = ("baseline_scr_mg_dl", "delta_hours", "cystatin_c_mg_l",
                "potassium_meq_l", "crrt_effluent_ml_kg_h")
    for key in (*required, *optional):
        value = case.get(key)
        if key in optional and value in (None, ""):
            continue
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError):
            raise ValueError(f"{key} needs a finite number.") from None
        if isinstance(value, bool) or not math.isfinite(number) or number <= 0:
            raise ValueError(f"{key} needs a finite positive number.")
    choices = {
        "sex": (None, {"male", "female", "m", "f"}),
        "scr_unit": ("mg_dl", {"mg_dl", "mg/dl", "umol_l", "umol/l"}),
        "rrt_modality": ("none", {"none", "ihd", "pd", "crrt"}),
        "weight_override": ("auto", {"auto", "abw", "ibw", "adjbw"}),
    }
    for key, (default, allowed) in choices.items():
        value = case.get(key, default)
        if not isinstance(value, str) or value.strip().lower() not in allowed:
            raise ValueError(f"Choose a supported value for {key}.")
        normalized = value.strip().lower()
        case[key] = {"abw": "ABW", "ibw": "IBW", "adjbw": "AdjBW"}.get(normalized, normalized) if key == "weight_override" else normalized
    for key in ("id", "name", "room", "primary_diagnosis", "signed_by"):
        if key in case and (not isinstance(case[key], str) or len(case[key]) > 300):
            raise ValueError(f"{key} must be text of at most 300 characters.")
    if "/" in case.get("id", "") or case.get("id", "") != case.get("id", "").strip():
        raise ValueError("Case ID cannot include a slash or surrounding spaces.")
    medications = case.get("medications", [])
    if not isinstance(medications, list) or len(medications) > 100:
        raise ValueError("Enter a list of up to 100 medications.")
    for index, item in enumerate(medications, 1):
        drug = item.get("drug_id") if isinstance(item, dict) else None
        if not isinstance(drug, str) or drug not in FORMULARY:
            raise ValueError(f"Medication {index} must be selected from the formulary.")
        dose = item.get("current_dose", "")
        if not isinstance(dose, str) or len(dose) > 300:
            raise ValueError(f"Medication {index} dose must be text of at most 300 characters.")
    return case
