"""Seed reference tables: NDC, CPT, ICD-10 with realistic healthcare data."""

from decimal import Decimal

# ──────────────────────────────────────────────
# CPT / HCPCS codes with CMS fee schedule prices
# ──────────────────────────────────────────────
CPT_CODES = [
    # E&M Office Visits
    {"cpt_code": "99211", "description": "Office visit, established, minimal", "category": "E&M", "facility_price": Decimal("23.00"), "non_facility_price": Decimal("45.00"), "rvu_work": Decimal("0.18"), "is_outpatient_typical": True},
    {"cpt_code": "99212", "description": "Office visit, established, straightforward", "category": "E&M", "facility_price": Decimal("45.00"), "non_facility_price": Decimal("76.00"), "rvu_work": Decimal("0.48"), "is_outpatient_typical": True},
    {"cpt_code": "99213", "description": "Office visit, established, low complexity", "category": "E&M", "facility_price": Decimal("65.00"), "non_facility_price": Decimal("110.00"), "rvu_work": Decimal("0.97"), "is_outpatient_typical": True},
    {"cpt_code": "99214", "description": "Office visit, established, moderate complexity", "category": "E&M", "facility_price": Decimal("95.00"), "non_facility_price": Decimal("145.00"), "rvu_work": Decimal("1.50"), "is_outpatient_typical": True},
    {"cpt_code": "99215", "description": "Office visit, established, high complexity", "category": "E&M", "facility_price": Decimal("130.00"), "non_facility_price": Decimal("200.00"), "rvu_work": Decimal("2.11"), "is_outpatient_typical": True},
    {"cpt_code": "99201", "description": "Office visit, new patient, straightforward", "category": "E&M", "facility_price": Decimal("45.00"), "non_facility_price": Decimal("75.00"), "rvu_work": Decimal("0.48"), "is_outpatient_typical": True},
    {"cpt_code": "99202", "description": "Office visit, new patient, straightforward", "category": "E&M", "facility_price": Decimal("65.00"), "non_facility_price": Decimal("110.00"), "rvu_work": Decimal("0.93"), "is_outpatient_typical": True},
    {"cpt_code": "99203", "description": "Office visit, new patient, low complexity", "category": "E&M", "facility_price": Decimal("95.00"), "non_facility_price": Decimal("150.00"), "rvu_work": Decimal("1.60"), "is_outpatient_typical": True},
    {"cpt_code": "99204", "description": "Office visit, new patient, moderate complexity", "category": "E&M", "facility_price": Decimal("140.00"), "non_facility_price": Decimal("210.00"), "rvu_work": Decimal("2.60"), "is_outpatient_typical": True},
    {"cpt_code": "99205", "description": "Office visit, new patient, high complexity", "category": "E&M", "facility_price": Decimal("170.00"), "non_facility_price": Decimal("265.00"), "rvu_work": Decimal("3.50"), "is_outpatient_typical": True},
    # E&M Hospital
    {"cpt_code": "99221", "description": "Initial hospital care, straightforward/low", "category": "E&M", "facility_price": Decimal("185.00"), "non_facility_price": Decimal("185.00"), "rvu_work": Decimal("2.00")},
    {"cpt_code": "99222", "description": "Initial hospital care, moderate", "category": "E&M", "facility_price": Decimal("250.00"), "non_facility_price": Decimal("250.00"), "rvu_work": Decimal("2.61")},
    {"cpt_code": "99223", "description": "Initial hospital care, high complexity", "category": "E&M", "facility_price": Decimal("340.00"), "non_facility_price": Decimal("340.00"), "rvu_work": Decimal("3.86")},
    {"cpt_code": "99281", "description": "ED visit, self-limited/minor", "category": "E&M", "facility_price": Decimal("50.00"), "non_facility_price": Decimal("50.00"), "rvu_work": Decimal("0.25")},
    {"cpt_code": "99283", "description": "ED visit, moderate severity", "category": "E&M", "facility_price": Decimal("120.00"), "non_facility_price": Decimal("120.00"), "rvu_work": Decimal("1.42")},
    {"cpt_code": "99285", "description": "ED visit, high severity with threat to life", "category": "E&M", "facility_price": Decimal("220.00"), "non_facility_price": Decimal("220.00"), "rvu_work": Decimal("3.80")},
    # Telehealth
    {"cpt_code": "99441", "description": "Telephone E&M, 5-10 min", "category": "E&M", "facility_price": Decimal("35.00"), "non_facility_price": Decimal("55.00"), "rvu_work": Decimal("0.25"), "is_outpatient_typical": True},
    {"cpt_code": "99442", "description": "Telephone E&M, 11-20 min", "category": "E&M", "facility_price": Decimal("65.00"), "non_facility_price": Decimal("95.00"), "rvu_work": Decimal("0.50"), "is_outpatient_typical": True},
    {"cpt_code": "99443", "description": "Telephone E&M, 21-30 min", "category": "E&M", "facility_price": Decimal("95.00"), "non_facility_price": Decimal("130.00"), "rvu_work": Decimal("0.75"), "is_outpatient_typical": True},
    # Surgery
    {"cpt_code": "27447", "description": "Total knee arthroplasty", "category": "Surgery", "facility_price": Decimal("1850.00"), "non_facility_price": Decimal("2200.00"), "rvu_work": Decimal("22.69")},
    {"cpt_code": "27130", "description": "Total hip arthroplasty", "category": "Surgery", "facility_price": Decimal("1750.00"), "non_facility_price": Decimal("2100.00"), "rvu_work": Decimal("22.22")},
    {"cpt_code": "29881", "description": "Arthroscopy, knee, with meniscectomy", "category": "Surgery", "facility_price": Decimal("680.00"), "non_facility_price": Decimal("1200.00"), "rvu_work": Decimal("6.30"), "is_outpatient_typical": True},
    {"cpt_code": "47562", "description": "Laparoscopic cholecystectomy", "category": "Surgery", "facility_price": Decimal("850.00"), "non_facility_price": Decimal("1500.00"), "rvu_work": Decimal("10.34")},
    {"cpt_code": "43239", "description": "Upper GI endoscopy with biopsy", "category": "Surgery", "facility_price": Decimal("320.00"), "non_facility_price": Decimal("520.00"), "rvu_work": Decimal("3.70"), "is_outpatient_typical": True},
    {"cpt_code": "45380", "description": "Colonoscopy with biopsy", "category": "Surgery", "facility_price": Decimal("350.00"), "non_facility_price": Decimal("550.00"), "rvu_work": Decimal("4.43"), "is_outpatient_typical": True},
    {"cpt_code": "10060", "description": "Incision and drainage of abscess", "category": "Surgery", "facility_price": Decimal("180.00"), "non_facility_price": Decimal("280.00"), "rvu_work": Decimal("1.22"), "is_outpatient_typical": True},
    # Radiology
    {"cpt_code": "73721", "description": "MRI knee without contrast", "category": "Radiology", "facility_price": Decimal("250.00"), "non_facility_price": Decimal("450.00"), "rvu_work": Decimal("1.09"), "is_outpatient_typical": True},
    {"cpt_code": "73221", "description": "MRI shoulder without contrast", "category": "Radiology", "facility_price": Decimal("250.00"), "non_facility_price": Decimal("450.00"), "rvu_work": Decimal("1.09"), "is_outpatient_typical": True},
    {"cpt_code": "70553", "description": "MRI brain with and without contrast", "category": "Radiology", "facility_price": Decimal("350.00"), "non_facility_price": Decimal("600.00"), "rvu_work": Decimal("1.98"), "is_outpatient_typical": True},
    {"cpt_code": "71046", "description": "Chest X-ray, 2 views", "category": "Radiology", "facility_price": Decimal("30.00"), "non_facility_price": Decimal("55.00"), "rvu_work": Decimal("0.18"), "is_outpatient_typical": True},
    {"cpt_code": "74177", "description": "CT abdomen and pelvis with contrast", "category": "Radiology", "facility_price": Decimal("290.00"), "non_facility_price": Decimal("480.00"), "rvu_work": Decimal("1.82"), "is_outpatient_typical": True},
    {"cpt_code": "77067", "description": "Screening mammography, bilateral", "category": "Radiology", "facility_price": Decimal("120.00"), "non_facility_price": Decimal("200.00"), "rvu_work": Decimal("0.70"), "is_outpatient_typical": True},
    # Lab / Diagnostic
    {"cpt_code": "80048", "description": "Basic metabolic panel", "category": "Lab", "facility_price": Decimal("18.00"), "non_facility_price": Decimal("18.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True,
     "bundled_codes": {"components": ["82310", "82374", "82435", "82565", "82947", "84132", "84295", "84520"]}},
    {"cpt_code": "80053", "description": "Comprehensive metabolic panel", "category": "Lab", "facility_price": Decimal("22.00"), "non_facility_price": Decimal("22.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "85025", "description": "Complete blood count (CBC) with diff", "category": "Lab", "facility_price": Decimal("12.00"), "non_facility_price": Decimal("12.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "82310", "description": "Calcium, total", "category": "Lab", "facility_price": Decimal("8.00"), "non_facility_price": Decimal("8.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "82374", "description": "Carbon dioxide (bicarbonate)", "category": "Lab", "facility_price": Decimal("7.00"), "non_facility_price": Decimal("7.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "82435", "description": "Chloride", "category": "Lab", "facility_price": Decimal("7.00"), "non_facility_price": Decimal("7.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "82565", "description": "Creatinine", "category": "Lab", "facility_price": Decimal("8.00"), "non_facility_price": Decimal("8.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "82947", "description": "Glucose, quantitative", "category": "Lab", "facility_price": Decimal("6.00"), "non_facility_price": Decimal("6.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "84132", "description": "Potassium", "category": "Lab", "facility_price": Decimal("7.00"), "non_facility_price": Decimal("7.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "84295", "description": "Sodium", "category": "Lab", "facility_price": Decimal("7.00"), "non_facility_price": Decimal("7.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "84520", "description": "Urea nitrogen (BUN)", "category": "Lab", "facility_price": Decimal("7.00"), "non_facility_price": Decimal("7.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "83036", "description": "Hemoglobin A1c", "category": "Lab", "facility_price": Decimal("15.00"), "non_facility_price": Decimal("15.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "80061", "description": "Lipid panel", "category": "Lab", "facility_price": Decimal("20.00"), "non_facility_price": Decimal("20.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "84443", "description": "Thyroid stimulating hormone (TSH)", "category": "Lab", "facility_price": Decimal("22.00"), "non_facility_price": Decimal("22.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    {"cpt_code": "81001", "description": "Urinalysis with microscopy", "category": "Lab", "facility_price": Decimal("5.00"), "non_facility_price": Decimal("5.00"), "rvu_work": Decimal("0.00"), "is_lab_diagnostic": True, "is_outpatient_typical": True},
    # DME
    {"cpt_code": "K0856", "description": "Power wheelchair, group 3, sling/solid seat", "category": "DME", "facility_price": Decimal("5500.00"), "non_facility_price": Decimal("5500.00"), "rvu_work": Decimal("0.00"), "is_dme": True},
    {"cpt_code": "K0823", "description": "Power wheelchair, group 2, captain seat", "category": "DME", "facility_price": Decimal("3500.00"), "non_facility_price": Decimal("3500.00"), "rvu_work": Decimal("0.00"), "is_dme": True},
    {"cpt_code": "E0601", "description": "CPAP device", "category": "DME", "facility_price": Decimal("800.00"), "non_facility_price": Decimal("800.00"), "rvu_work": Decimal("0.00"), "is_dme": True},
    {"cpt_code": "L1832", "description": "Knee brace, adjustable", "category": "DME", "facility_price": Decimal("450.00"), "non_facility_price": Decimal("450.00"), "rvu_work": Decimal("0.00"), "is_dme": True},
    # Physical therapy
    {"cpt_code": "97110", "description": "Therapeutic exercises, 15 min", "category": "Medicine", "facility_price": Decimal("35.00"), "non_facility_price": Decimal("55.00"), "rvu_work": Decimal("0.45"), "is_outpatient_typical": True},
    {"cpt_code": "97140", "description": "Manual therapy, 15 min", "category": "Medicine", "facility_price": Decimal("32.00"), "non_facility_price": Decimal("50.00"), "rvu_work": Decimal("0.43"), "is_outpatient_typical": True},
    # Mental health
    {"cpt_code": "90834", "description": "Psychotherapy, 45 min", "category": "Medicine", "facility_price": Decimal("100.00"), "non_facility_price": Decimal("130.00"), "rvu_work": Decimal("1.67"), "is_outpatient_typical": True},
    {"cpt_code": "90837", "description": "Psychotherapy, 60 min", "category": "Medicine", "facility_price": Decimal("135.00"), "non_facility_price": Decimal("170.00"), "rvu_work": Decimal("2.35"), "is_outpatient_typical": True},
]

# Set defaults for optional fields
for code in CPT_CODES:
    code.setdefault("rvu_practice", Decimal("0.50"))
    code.setdefault("rvu_malpractice", Decimal("0.05"))
    code.setdefault("global_period", "XXX")
    code.setdefault("bundled_codes", None)
    code.setdefault("is_outpatient_typical", False)
    code.setdefault("is_lab_diagnostic", False)
    code.setdefault("is_dme", False)


# ──────────────────────────────────────────────
# ICD-10-CM Diagnosis Codes
# ──────────────────────────────────────────────
ICD_CODES = [
    # Diabetes
    {"icd_code": "E11.9", "description": "Type 2 diabetes mellitus without complications", "category": "Endocrine", "valid_cpt_codes": ["99211", "99212", "99213", "99214", "99215", "83036", "80048", "80053", "85025"], "gender_specific": None},
    {"icd_code": "E11.65", "description": "Type 2 diabetes with hyperglycemia", "category": "Endocrine", "valid_cpt_codes": ["99213", "99214", "99215", "83036", "80048", "80053"], "gender_specific": None},
    {"icd_code": "E10.9", "description": "Type 1 diabetes mellitus without complications", "category": "Endocrine", "valid_cpt_codes": ["99211", "99212", "99213", "99214", "99215", "83036", "80048"], "gender_specific": None},
    # Hypertension
    {"icd_code": "I10", "description": "Essential (primary) hypertension", "category": "Circulatory", "valid_cpt_codes": ["99211", "99212", "99213", "99214", "99215", "80048", "80053", "85025", "80061"], "gender_specific": None},
    {"icd_code": "I25.10", "description": "Atherosclerotic heart disease of native artery", "category": "Circulatory", "valid_cpt_codes": ["99213", "99214", "99215", "80061", "85025"], "gender_specific": None},
    {"icd_code": "I50.9", "description": "Heart failure, unspecified", "category": "Circulatory", "valid_cpt_codes": ["99214", "99215", "99222", "99223", "71046", "80053", "85025"], "gender_specific": None},
    # Respiratory
    {"icd_code": "J00", "description": "Acute nasopharyngitis (common cold)", "category": "Respiratory", "valid_cpt_codes": ["99211", "99212", "99213"], "gender_specific": None},
    {"icd_code": "J06.9", "description": "Acute upper respiratory infection, unspecified", "category": "Respiratory", "valid_cpt_codes": ["99211", "99212", "99213"], "gender_specific": None},
    {"icd_code": "J18.9", "description": "Pneumonia, unspecified organism", "category": "Respiratory", "valid_cpt_codes": ["99214", "99215", "99222", "99223", "71046", "85025"], "gender_specific": None},
    {"icd_code": "J45.20", "description": "Mild intermittent asthma, uncomplicated", "category": "Respiratory", "valid_cpt_codes": ["99213", "99214", "71046"], "gender_specific": None},
    {"icd_code": "J44.1", "description": "COPD with acute exacerbation", "category": "Respiratory", "valid_cpt_codes": ["99214", "99215", "99222", "71046", "85025"], "gender_specific": None},
    # Musculoskeletal
    {"icd_code": "M17.11", "description": "Primary osteoarthritis, right knee", "category": "Musculoskeletal", "valid_cpt_codes": ["99213", "99214", "73721", "29881", "27447", "97110"], "gender_specific": None},
    {"icd_code": "M17.12", "description": "Primary osteoarthritis, left knee", "category": "Musculoskeletal", "valid_cpt_codes": ["99213", "99214", "73721", "29881", "27447", "97110"], "gender_specific": None},
    {"icd_code": "M54.5", "description": "Low back pain", "category": "Musculoskeletal", "valid_cpt_codes": ["99213", "99214", "97110", "97140", "74177"], "gender_specific": None},
    {"icd_code": "M75.111", "description": "Rotator cuff tear, right shoulder", "category": "Musculoskeletal", "valid_cpt_codes": ["99214", "73221", "97110"], "gender_specific": None},
    {"icd_code": "M16.11", "description": "Primary osteoarthritis, right hip", "category": "Musculoskeletal", "valid_cpt_codes": ["99213", "99214", "27130", "97110"], "gender_specific": None},
    # Mental health
    {"icd_code": "F32.1", "description": "Major depressive disorder, single episode, moderate", "category": "Mental", "valid_cpt_codes": ["99213", "99214", "90834", "90837"], "gender_specific": None},
    {"icd_code": "F41.1", "description": "Generalized anxiety disorder", "category": "Mental", "valid_cpt_codes": ["99213", "99214", "90834", "90837"], "gender_specific": None},
    # GI
    {"icd_code": "K21.0", "description": "GERD with esophagitis", "category": "Digestive", "valid_cpt_codes": ["99213", "99214", "43239"], "gender_specific": None},
    {"icd_code": "K80.20", "description": "Calculus of gallbladder without cholecystitis", "category": "Digestive", "valid_cpt_codes": ["99214", "47562", "74177"], "gender_specific": None},
    # Gender-specific
    {"icd_code": "N40.0", "description": "Benign prostatic hyperplasia without LUTS", "category": "Genitourinary", "valid_cpt_codes": ["99213", "99214", "81001"], "gender_specific": "M"},
    {"icd_code": "N63.10", "description": "Unspecified lump in right breast", "category": "Neoplasms", "valid_cpt_codes": ["99214", "77067"], "gender_specific": "F"},
    {"icd_code": "Z12.31", "description": "Encounter for screening mammogram", "category": "Factors", "valid_cpt_codes": ["77067"], "gender_specific": "F"},
    # Age-related
    {"icd_code": "M80.08XA", "description": "Age-related osteoporosis with pathological fracture", "category": "Musculoskeletal", "valid_cpt_codes": ["99214", "99215"], "gender_specific": None, "age_range_min": 50},
    # Injury / skin
    {"icd_code": "L02.211", "description": "Cutaneous abscess of abdominal wall", "category": "Skin", "valid_cpt_codes": ["10060", "99213"], "gender_specific": None},
    # Preventive
    {"icd_code": "Z00.00", "description": "Encounter for general adult medical exam without abnormal findings", "category": "Factors", "valid_cpt_codes": ["99213", "99214", "80048", "80053", "85025", "80061", "84443"], "gender_specific": None},
    {"icd_code": "Z23", "description": "Encounter for immunization", "category": "Factors", "valid_cpt_codes": ["99211", "99212"], "gender_specific": None},
    # Pain management (relevant for opioid prescribing)
    {"icd_code": "G89.29", "description": "Other chronic pain", "category": "Nervous", "valid_cpt_codes": ["99213", "99214", "99215", "97110", "97140"], "gender_specific": None},
    {"icd_code": "G89.4", "description": "Chronic pain syndrome", "category": "Nervous", "valid_cpt_codes": ["99214", "99215", "97110"], "gender_specific": None},
    # Neoplasms
    {"icd_code": "C50.911", "description": "Malignant neoplasm of right breast", "category": "Neoplasms", "valid_cpt_codes": ["99214", "99215", "77067", "99223"], "gender_specific": "F"},
    {"icd_code": "C34.90", "description": "Malignant neoplasm of lung, unspecified", "category": "Neoplasms", "valid_cpt_codes": ["99214", "99215", "71046", "74177", "99223"], "gender_specific": None},
]

# Set defaults
for code in ICD_CODES:
    code.setdefault("is_billable", True)
    code.setdefault("gender_specific", None)
    code.setdefault("age_range_min", None)
    code.setdefault("age_range_max", None)
    code.setdefault("valid_cpt_codes", [])


# ──────────────────────────────────────────────
# NDC (National Drug Code) Directory
# ──────────────────────────────────────────────
NDC_CODES = [
    # Opioids (Schedule II)
    {"ndc_code": "00591024401", "proprietary_name": "Oxycodone HCl", "nonproprietary_name": "Oxycodone", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Oxycodone Hydrochloride", "dea_schedule": "CII", "therapeutic_class": "Opioid Analgesic", "avg_wholesale_price": Decimal("85.00"), "unit_price": Decimal("2.83"), "generic_available": True, "generic_ndc": "00591024401", "generic_price": Decimal("85.00")},
    {"ndc_code": "00406052301", "proprietary_name": "Hydrocodone-APAP", "nonproprietary_name": "Hydrocodone/Acetaminophen", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Hydrocodone Bitartrate", "dea_schedule": "CII", "therapeutic_class": "Opioid Analgesic", "avg_wholesale_price": Decimal("45.00"), "unit_price": Decimal("0.75"), "generic_available": True, "generic_ndc": "00406052301", "generic_price": Decimal("45.00")},
    {"ndc_code": "12634058001", "proprietary_name": "OxyContin", "nonproprietary_name": "Oxycodone ER", "dosage_form": "TABLET, EXTENDED RELEASE", "route": "ORAL", "substance_name": "Oxycodone Hydrochloride", "dea_schedule": "CII", "therapeutic_class": "Opioid Analgesic", "avg_wholesale_price": Decimal("350.00"), "unit_price": Decimal("11.67"), "generic_available": True, "generic_ndc": "00591024401", "generic_price": Decimal("120.00")},
    {"ndc_code": "00228206611", "proprietary_name": "Morphine Sulfate", "nonproprietary_name": "Morphine", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Morphine Sulfate", "dea_schedule": "CII", "therapeutic_class": "Opioid Analgesic", "avg_wholesale_price": Decimal("55.00"), "unit_price": Decimal("1.83"), "generic_available": True, "generic_ndc": "00228206611", "generic_price": Decimal("55.00")},
    {"ndc_code": "43063018420", "proprietary_name": "Fentanyl Patch", "nonproprietary_name": "Fentanyl Transdermal", "dosage_form": "PATCH", "route": "TRANSDERMAL", "substance_name": "Fentanyl", "dea_schedule": "CII", "therapeutic_class": "Opioid Analgesic", "avg_wholesale_price": Decimal("180.00"), "unit_price": Decimal("36.00"), "generic_available": True, "generic_ndc": "43063018420", "generic_price": Decimal("180.00")},
    # Benzodiazepines (Schedule IV)
    {"ndc_code": "00591024001", "proprietary_name": "Alprazolam", "nonproprietary_name": "Alprazolam", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Alprazolam", "dea_schedule": "CIV", "therapeutic_class": "Benzodiazepine", "avg_wholesale_price": Decimal("25.00"), "unit_price": Decimal("0.42"), "generic_available": True, "generic_ndc": "00591024001", "generic_price": Decimal("25.00")},
    {"ndc_code": "00781106201", "proprietary_name": "Diazepam", "nonproprietary_name": "Diazepam", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Diazepam", "dea_schedule": "CIV", "therapeutic_class": "Benzodiazepine", "avg_wholesale_price": Decimal("20.00"), "unit_price": Decimal("0.33"), "generic_available": True, "generic_ndc": "00781106201", "generic_price": Decimal("20.00")},
    # Stimulants (Schedule II)
    {"ndc_code": "00555097702", "proprietary_name": "Adderall", "nonproprietary_name": "Amphetamine/Dextroamphetamine", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Amphetamine Mixed Salts", "dea_schedule": "CII", "therapeutic_class": "CNS Stimulant", "avg_wholesale_price": Decimal("280.00"), "unit_price": Decimal("9.33"), "generic_available": True, "generic_ndc": "00555097702", "generic_price": Decimal("75.00")},
    # Common non-controlled
    {"ndc_code": "00071015523", "proprietary_name": "Lipitor", "nonproprietary_name": "Atorvastatin", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Atorvastatin Calcium", "dea_schedule": None, "therapeutic_class": "Statin", "avg_wholesale_price": Decimal("350.00"), "unit_price": Decimal("11.67"), "generic_available": True, "generic_ndc": "68180063602", "generic_price": Decimal("15.00")},
    {"ndc_code": "68180063602", "proprietary_name": "Atorvastatin Calcium", "nonproprietary_name": "Atorvastatin", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Atorvastatin Calcium", "dea_schedule": None, "therapeutic_class": "Statin", "avg_wholesale_price": Decimal("15.00"), "unit_price": Decimal("0.50"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "00378001001", "proprietary_name": "Metformin HCl", "nonproprietary_name": "Metformin", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Metformin Hydrochloride", "dea_schedule": None, "therapeutic_class": "Antidiabetic", "avg_wholesale_price": Decimal("12.00"), "unit_price": Decimal("0.20"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "00093505801", "proprietary_name": "Lisinopril", "nonproprietary_name": "Lisinopril", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Lisinopril", "dea_schedule": None, "therapeutic_class": "ACE Inhibitor", "avg_wholesale_price": Decimal("15.00"), "unit_price": Decimal("0.25"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "00378180177", "proprietary_name": "Amlodipine", "nonproprietary_name": "Amlodipine", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Amlodipine Besylate", "dea_schedule": None, "therapeutic_class": "Calcium Channel Blocker", "avg_wholesale_price": Decimal("18.00"), "unit_price": Decimal("0.30"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "63304083005", "proprietary_name": "Omeprazole", "nonproprietary_name": "Omeprazole", "dosage_form": "CAPSULE", "route": "ORAL", "substance_name": "Omeprazole", "dea_schedule": None, "therapeutic_class": "PPI", "avg_wholesale_price": Decimal("22.00"), "unit_price": Decimal("0.37"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "00069015001", "proprietary_name": "Zoloft", "nonproprietary_name": "Sertraline", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Sertraline Hydrochloride", "dea_schedule": None, "therapeutic_class": "SSRI", "avg_wholesale_price": Decimal("280.00"), "unit_price": Decimal("9.33"), "generic_available": True, "generic_ndc": "16714068501", "generic_price": Decimal("12.00")},
    {"ndc_code": "16714068501", "proprietary_name": "Sertraline HCl", "nonproprietary_name": "Sertraline", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Sertraline Hydrochloride", "dea_schedule": None, "therapeutic_class": "SSRI", "avg_wholesale_price": Decimal("12.00"), "unit_price": Decimal("0.20"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "00069425041", "proprietary_name": "Celebrex", "nonproprietary_name": "Celecoxib", "dosage_form": "CAPSULE", "route": "ORAL", "substance_name": "Celecoxib", "dea_schedule": None, "therapeutic_class": "NSAID", "avg_wholesale_price": Decimal("320.00"), "unit_price": Decimal("10.67"), "generic_available": True, "generic_ndc": "62332003190", "generic_price": Decimal("25.00")},
    {"ndc_code": "62332003190", "proprietary_name": "Celecoxib", "nonproprietary_name": "Celecoxib", "dosage_form": "CAPSULE", "route": "ORAL", "substance_name": "Celecoxib", "dea_schedule": None, "therapeutic_class": "NSAID", "avg_wholesale_price": Decimal("25.00"), "unit_price": Decimal("0.42"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    # Antibiotics
    {"ndc_code": "00093315201", "proprietary_name": "Amoxicillin", "nonproprietary_name": "Amoxicillin", "dosage_form": "CAPSULE", "route": "ORAL", "substance_name": "Amoxicillin", "dea_schedule": None, "therapeutic_class": "Antibiotic", "avg_wholesale_price": Decimal("10.00"), "unit_price": Decimal("0.17"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "00093317431", "proprietary_name": "Azithromycin", "nonproprietary_name": "Azithromycin", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Azithromycin", "dea_schedule": None, "therapeutic_class": "Antibiotic", "avg_wholesale_price": Decimal("35.00"), "unit_price": Decimal("5.83"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    # Compound drugs (high cost)
    {"ndc_code": "COMPOUND001", "proprietary_name": "Custom Pain Compound", "nonproprietary_name": "Ketamine/Gabapentin/Baclofen Cream", "dosage_form": "CREAM", "route": "TOPICAL", "substance_name": "Compound", "dea_schedule": None, "therapeutic_class": "Compound", "avg_wholesale_price": Decimal("5000.00"), "unit_price": Decimal("166.67"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    {"ndc_code": "COMPOUND002", "proprietary_name": "Custom Scar Compound", "nonproprietary_name": "Silicone/Vitamin E/Tretinoin Cream", "dosage_form": "CREAM", "route": "TOPICAL", "substance_name": "Compound", "dea_schedule": None, "therapeutic_class": "Compound", "avg_wholesale_price": Decimal("8000.00"), "unit_price": Decimal("266.67"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    # Insulin
    {"ndc_code": "00169750111", "proprietary_name": "Lantus", "nonproprietary_name": "Insulin Glargine", "dosage_form": "SOLUTION", "route": "INJECTABLE", "substance_name": "Insulin Glargine", "dea_schedule": None, "therapeutic_class": "Insulin", "avg_wholesale_price": Decimal("380.00"), "unit_price": Decimal("38.00"), "generic_available": True, "generic_ndc": "00169413212", "generic_price": Decimal("150.00")},
    {"ndc_code": "00169413212", "proprietary_name": "Basaglar", "nonproprietary_name": "Insulin Glargine", "dosage_form": "SOLUTION", "route": "INJECTABLE", "substance_name": "Insulin Glargine", "dea_schedule": None, "therapeutic_class": "Insulin", "avg_wholesale_price": Decimal("150.00"), "unit_price": Decimal("15.00"), "generic_available": False, "generic_ndc": None, "generic_price": None},
    # Blood thinner
    {"ndc_code": "63653114204", "proprietary_name": "Eliquis", "nonproprietary_name": "Apixaban", "dosage_form": "TABLET", "route": "ORAL", "substance_name": "Apixaban", "dea_schedule": None, "therapeutic_class": "Anticoagulant", "avg_wholesale_price": Decimal("550.00"), "unit_price": Decimal("9.17"), "generic_available": False, "generic_ndc": None, "generic_price": None},
]
