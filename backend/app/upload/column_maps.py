"""
Column mapping aliases for CSV upload auto-detection.

Each key is our internal field name; the value is a list of common
aliases (lowercased, stripped of spaces/underscores) that client CSVs
might use.
"""

MEDICAL_REQUIRED: dict[str, list[str]] = {
    "claim_id": ["claimid", "claimnumber", "claimno", "clmid", "claim_id", "claim_number"],
    "member_id": ["memberid", "membernumber", "subscriberid", "mbrid", "member_id", "subscriber_id", "patientid", "patient_id"],
    "provider_npi": ["npi", "providernpi", "renderingnpi", "billingnpi", "provider_npi", "rendering_npi"],
    "service_date": ["servicedate", "dos", "dateofservice", "svcdate", "service_date", "date_of_service"],
    "cpt_code": ["cptcode", "cpt", "procedurecode", "proccode", "hcpcs", "cpt_code", "procedure_code"],
    "diagnosis_code_primary": ["diagnosiscode", "dxcode", "icdcode", "primarydx", "dx1", "diagnosis_code", "dx_code", "icd_code", "primary_dx", "diagnosis_code_primary"],
    "amount_billed": ["amountbilled", "billedamount", "chargeamount", "totalcharge", "amount_billed", "billed_amount", "charge_amount", "total_charge"],
}

MEDICAL_OPTIONAL: dict[str, list[str]] = {
    "amount_allowed": ["amountallowed", "allowedamount", "amount_allowed", "allowed_amount"],
    "amount_paid": ["amountpaid", "paidamount", "amount_paid", "paid_amount"],
    "place_of_service": ["placeofservice", "pos", "place_of_service"],
    "cpt_modifier": ["modifier", "cptmodifier", "cpt_modifier"],
    "diagnosis_code_2": ["dx2", "diagnosiscode2", "diagnosis_code_2"],
    "diagnosis_code_3": ["dx3", "diagnosiscode3", "diagnosis_code_3"],
    "diagnosis_code_4": ["dx4", "diagnosiscode4", "diagnosis_code_4"],
    "units": ["units", "qty", "quantity", "serviceunits"],
    "claim_type": ["claimtype", "claim_type", "typeofsvc"],
    "plan_id": ["planid", "plan_id", "groupnumber"],
}

PHARMACY_REQUIRED: dict[str, list[str]] = {
    "claim_id": ["claimid", "claimnumber", "rxnumber", "rxno", "claim_id", "rx_number"],
    "member_id": ["memberid", "membernumber", "subscriberid", "patientid", "member_id", "patient_id"],
    "prescriber_npi": ["prescribernpi", "prescriber_npi", "prescribingnpi", "doctornpi", "npi"],
    "pharmacy_npi": ["pharmacynpi", "pharmacy_npi", "dispensingnpi", "storenpi"],
    "fill_date": ["filldate", "fill_date", "dispenseddate", "dispensed_date", "rxdate", "datewritten"],
    "ndc_code": ["ndccode", "ndc", "ndc_code", "nationaldrugcode"],
    "drug_name": ["drugname", "drug_name", "medication", "medicationname", "productname"],
    "amount_billed": ["amountbilled", "billedamount", "amount_billed", "billed_amount", "ingredientcost"],
}

PHARMACY_OPTIONAL: dict[str, list[str]] = {
    "amount_allowed": ["amountallowed", "amount_allowed", "allowedamount"],
    "amount_paid": ["amountpaid", "amount_paid", "paidamount"],
    "quantity_dispensed": ["quantity", "qty", "quantitydispensed", "quantity_dispensed"],
    "days_supply": ["dayssupply", "days_supply", "supplyday"],
    "refill_number": ["refillnumber", "refill_number", "refill", "refillno"],
    "drug_class": ["drugclass", "drug_class", "therapeuticclass"],
    "is_generic": ["isgeneric", "is_generic", "generic"],
    "is_controlled": ["iscontrolled", "is_controlled", "controlled"],
    "dea_schedule": ["deaschedule", "dea_schedule", "schedule"],
    "copay": ["copay", "copayment", "co_pay"],
}


def _normalize(name: str) -> str:
    """Lowercase, strip spaces/underscores/dashes for fuzzy matching."""
    return name.lower().replace(" ", "").replace("_", "").replace("-", "")


def auto_map_columns(
    csv_headers: list[str],
    claim_type: str = "medical",
) -> dict[str, str | None]:
    """
    Given a list of CSV column headers, return a mapping of
    our_field_name -> csv_header_name for each detected match.

    Returns dict where keys are internal field names and values
    are the matched CSV header (original casing) or None if no match.
    """
    required = MEDICAL_REQUIRED if claim_type == "medical" else PHARMACY_REQUIRED
    optional = MEDICAL_OPTIONAL if claim_type == "medical" else PHARMACY_OPTIONAL

    all_fields = {**required, **optional}
    normalized_headers = {_normalize(h): h for h in csv_headers}
    mapping: dict[str, str | None] = {}

    for field_name, aliases in all_fields.items():
        matched = None
        for alias in aliases:
            norm_alias = _normalize(alias)
            if norm_alias in normalized_headers:
                matched = normalized_headers[norm_alias]
                break
        mapping[field_name] = matched

    return mapping
