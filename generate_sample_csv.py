#!/usr/bin/env python3
"""
Generate sample medical and pharmacy claims CSV files with embedded fraud patterns
for testing an FWA (Fraud, Waste, Abuse) detection system upload wizard.
"""

import csv
import os
import random
from datetime import date, timedelta

random.seed(42)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")
MEDICAL_CSV = os.path.join(OUTPUT_DIR, "sample_medical_claims.csv")
PHARMACY_CSV = os.path.join(OUTPUT_DIR, "sample_pharmacy_claims.csv")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DATE_START = date(2024, 6, 1)
DATE_END = date(2025, 9, 30)
DATE_RANGE_DAYS = (DATE_END - DATE_START).days


def random_date(start=DATE_START, end=DATE_END):
    return start + timedelta(days=random.randint(0, (end - start).days))


def fmt_date(d):
    return d.strftime("%m/%d/%Y")


def random_weekday_date():
    """Return a random date that falls on a weekday."""
    while True:
        d = random_date()
        if d.weekday() < 5:
            return d


def random_weekend_date():
    """Return a random date that falls on Saturday or Sunday."""
    while True:
        d = random_date()
        if d.weekday() >= 5:
            return d


def money(value):
    return round(value, 2)


# ---------------------------------------------------------------------------
# Medical claims configuration
# ---------------------------------------------------------------------------

PROVIDER_NPIS = [f"1{random.randint(100000000, 999999999)}" for _ in range(28)]
# Insert our two fraud-pattern providers at known positions
PROVIDER_NPIS_FRAUD_UPCODER = "1234567001"
PROVIDER_NPIS_FRAUD_WEEKEND = "1234567002"
PROVIDER_NPIS = [PROVIDER_NPIS_FRAUD_UPCODER, PROVIDER_NPIS_FRAUD_WEEKEND] + PROVIDER_NPIS[:28]
# Ensure exactly 30 unique
PROVIDER_NPIS = list(dict.fromkeys(PROVIDER_NPIS))[:30]

MEMBER_IDS = [f"MBR-{10000 + i}" for i in range(100)]
PLAN_IDS = [f"PLAN-{chr(65 + i)}{random.randint(100, 999)}" for i in range(15)]

CPT_CODES = [
    "99213", "99214", "99215",  # Office visits (low to high)
    "99232", "99233",            # Hospital visits
    "99243", "99244",            # Consultations
    "27447", "29881", "43239", "47562", "49505",  # Procedures
    "99283", "99284", "99285",   # ER visits
]

# Typical price ranges per CPT code
CPT_PRICE_RANGES = {
    "99213": (75, 200),
    "99214": (120, 300),
    "99215": (180, 450),
    "99232": (100, 250),
    "99233": (150, 350),
    "99243": (200, 500),
    "99244": (250, 600),
    "27447": (8000, 25000),
    "29881": (3000, 8000),
    "43239": (2000, 6000),
    "47562": (5000, 15000),
    "49505": (3000, 9000),
    "99283": (300, 800),
    "99284": (500, 1500),
    "99285": (800, 2500),
}

ICD10_CODES = [
    "M54.5", "M79.3", "E11.9", "I10", "J06.9",
    "Z00.00", "M17.11", "G89.29", "K21.0", "R10.9",
]

MEDICAL_HEADERS = [
    "Claim_ID", "Member_ID", "Provider_NPI", "Service_Date", "CPT_Code",
    "Diagnosis_Code", "Amount_Billed", "Amount_Allowed", "Amount_Paid",
    "Place_of_Service", "Modifier", "Units", "Plan_ID",
]

# Low-cost office visit CPT codes (for the "high billing" fraud pattern)
LOW_COST_CPTS = ["99213", "99214", "99232"]

MODIFIERS = ["", "", "", "", "", "25", "59", "76", ""]  # Mostly blank


def generate_normal_medical_claim(claim_id):
    provider = random.choice(PROVIDER_NPIS[2:])  # Skip fraud providers
    member = random.choice(MEMBER_IDS)
    plan = random.choice(PLAN_IDS)
    svc_date = random_weekday_date()
    cpt = random.choice(CPT_CODES)
    dx = random.choice(ICD10_CODES)
    low, high = CPT_PRICE_RANGES[cpt]
    billed = money(random.uniform(low, high))
    allowed = money(billed * random.uniform(0.70, 0.90))
    paid = money(allowed * random.uniform(0.80, 0.95))
    pos = random.choices(["11", "21", "23"], weights=[70, 20, 10])[0]
    modifier = random.choice(MODIFIERS)
    units = random.choices([1, 2, 3], weights=[80, 15, 5])[0]
    return [
        f"MC-{claim_id:06d}", member, provider, fmt_date(svc_date), cpt,
        dx, billed, allowed, paid, pos, modifier, units, plan,
    ]


# ---------------------------------------------------------------------------
# Medical fraud pattern generators
# ---------------------------------------------------------------------------

def generate_upcoding_claims(start_id):
    """FRAUD 1: Provider 1234567001 bills 99215 for >40 of 50 claims."""
    rows = []
    provider = PROVIDER_NPIS_FRAUD_UPCODER
    for i in range(50):
        claim_id = start_id + i
        member = random.choice(MEMBER_IDS)
        plan = random.choice(PLAN_IDS)
        svc_date = random_date()
        # >40 of 50 use 99215 (highest office visit)
        if i < 42:
            cpt = "99215"
        else:
            cpt = random.choice(["99213", "99214"])
        dx = random.choice(ICD10_CODES)
        low, high = CPT_PRICE_RANGES[cpt]
        billed = money(random.uniform(low, high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        pos = "11"
        modifier = random.choice(MODIFIERS)
        units = 1
        rows.append([
            f"MC-{claim_id:06d}", member, provider, fmt_date(svc_date), cpt,
            dx, billed, allowed, paid, pos, modifier, units, plan,
        ])
    return rows


def generate_duplicate_billing_claims(start_id):
    """FRAUD 2: 15 pairs of duplicate claims (same member+provider+date+CPT)."""
    rows = []
    for i in range(15):
        member = random.choice(MEMBER_IDS)
        provider = random.choice(PROVIDER_NPIS[2:])
        plan = random.choice(PLAN_IDS)
        svc_date = random_date()
        cpt = random.choice(CPT_CODES)
        dx = random.choice(ICD10_CODES)
        low, high = CPT_PRICE_RANGES[cpt]
        billed = money(random.uniform(low, high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        pos = random.choices(["11", "21", "23"], weights=[70, 20, 10])[0]
        modifier = random.choice(MODIFIERS)
        units = 1

        # First claim of the pair
        rows.append([
            f"MC-{start_id + 2 * i:06d}", member, provider, fmt_date(svc_date),
            cpt, dx, billed, allowed, paid, pos, modifier, units, plan,
        ])
        # Second (duplicate) claim – different Claim_ID, same details
        # Slight variation in billed amount to make it realistic
        billed2 = billed  # same billed
        allowed2 = money(billed2 * random.uniform(0.70, 0.90))
        paid2 = money(allowed2 * random.uniform(0.80, 0.95))
        rows.append([
            f"MC-{start_id + 2 * i + 1:06d}", member, provider, fmt_date(svc_date),
            cpt, dx, billed2, allowed2, paid2, pos, modifier, units, plan,
        ])
    return rows


def generate_high_billing_claims(start_id):
    """FRAUD 3: 10 claims with Amount_Billed > $15000 for low-cost CPTs."""
    rows = []
    for i in range(10):
        member = random.choice(MEMBER_IDS)
        provider = random.choice(PROVIDER_NPIS[2:])
        plan = random.choice(PLAN_IDS)
        svc_date = random_date()
        cpt = random.choice(LOW_COST_CPTS)
        dx = random.choice(ICD10_CODES)
        billed = money(random.uniform(15500, 24000))  # Way too high for office visit
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        pos = "11"
        modifier = random.choice(MODIFIERS)
        units = 1
        rows.append([
            f"MC-{start_id + i:06d}", member, provider, fmt_date(svc_date), cpt,
            dx, billed, allowed, paid, pos, modifier, units, plan,
        ])
    return rows


def generate_weekend_billing_claims(start_id):
    """FRAUD 4: Provider 1234567002 has 25 claims on weekends."""
    rows = []
    provider = PROVIDER_NPIS_FRAUD_WEEKEND
    for i in range(25):
        claim_id = start_id + i
        member = random.choice(MEMBER_IDS)
        plan = random.choice(PLAN_IDS)
        svc_date = random_weekend_date()
        cpt = random.choice(["99213", "99214", "99215"])
        dx = random.choice(ICD10_CODES)
        low, high = CPT_PRICE_RANGES[cpt]
        billed = money(random.uniform(low, high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        pos = "11"
        modifier = random.choice(MODIFIERS)
        units = 1
        rows.append([
            f"MC-{claim_id:06d}", member, provider, fmt_date(svc_date), cpt,
            dx, billed, allowed, paid, pos, modifier, units, plan,
        ])
    return rows


def generate_future_date_claims(start_id):
    """FRAUD 5: 5 claims with service_date in 2026."""
    rows = []
    future_start = date(2026, 1, 15)
    future_end = date(2026, 6, 30)
    for i in range(5):
        member = random.choice(MEMBER_IDS)
        provider = random.choice(PROVIDER_NPIS[2:])
        plan = random.choice(PLAN_IDS)
        svc_date = random_date(future_start, future_end)
        cpt = random.choice(CPT_CODES)
        dx = random.choice(ICD10_CODES)
        low, high = CPT_PRICE_RANGES[cpt]
        billed = money(random.uniform(low, high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        pos = random.choices(["11", "21", "23"], weights=[70, 20, 10])[0]
        modifier = random.choice(MODIFIERS)
        units = 1
        rows.append([
            f"MC-{start_id + i:06d}", member, provider, fmt_date(svc_date), cpt,
            dx, billed, allowed, paid, pos, modifier, units, plan,
        ])
    return rows


# ---------------------------------------------------------------------------
# Pharmacy claims configuration
# ---------------------------------------------------------------------------

PRESCRIBER_NPIS = [f"1{random.randint(100000000, 999999999)}" for _ in range(19)]
PRESCRIBER_NPIS_PILL_MILL = "1987654001"
PRESCRIBER_NPIS = [PRESCRIBER_NPIS_PILL_MILL] + PRESCRIBER_NPIS[:19]
PRESCRIBER_NPIS = list(dict.fromkeys(PRESCRIBER_NPIS))[:20]

PHARMACY_NPIS = [f"1{random.randint(100000000, 999999999)}" for _ in range(15)]
PHARMACY_NPIS = list(dict.fromkeys(PHARMACY_NPIS))[:15]

PHARMA_MEMBER_IDS = [f"MBR-{80000 + i}" for i in range(79)]
PHARMA_MEMBER_DOCTOR_SHOPPER = "MBR-90001"
PHARMA_MEMBER_IDS = [PHARMA_MEMBER_DOCTOR_SHOPPER] + PHARMA_MEMBER_IDS
PHARMA_MEMBER_IDS = list(dict.fromkeys(PHARMA_MEMBER_IDS))[:80]

# NDC -> (Drug_Name, Is_Controlled, DEA_Schedule, typical_price_low, typical_price_high, Is_Generic)
NDC_CATALOG = {
    "00002-4462-30": ("Oxycodone", True, "II", 50, 400, False),
    "00078-0357-05": ("Adderall", True, "II", 80, 350, False),
    "00591-0385-01": ("Lorazepam", True, "IV", 20, 150, True),
    "63304-0826-01": ("Gabapentin", False, "", 15, 120, True),
    "00093-7180-01": ("Lisinopril", False, "", 10, 60, True),
    "00074-3799-13": ("Humira", False, "", 3000, 8000, False),
    "00069-0145-01": ("Lipitor", False, "", 30, 200, False),
    "50090-3889-00": ("Metformin", False, "", 10, 50, True),
    "00173-0682-00": ("Advair", False, "", 150, 500, False),
    "00002-7140-01": ("Insulin", False, "", 100, 600, False),
}

CONTROLLED_NDCS = [ndc for ndc, info in NDC_CATALOG.items() if info[1]]
NON_CONTROLLED_NDCS = [ndc for ndc, info in NDC_CATALOG.items() if not info[1]]
GENERIC_NDCS = [ndc for ndc, info in NDC_CATALOG.items() if info[5]]

PHARMACY_HEADERS = [
    "Claim_ID", "Member_ID", "Prescriber_NPI", "Pharmacy_NPI", "Fill_Date",
    "NDC_Code", "Drug_Name", "Amount_Billed", "Amount_Allowed", "Amount_Paid",
    "Quantity", "Days_Supply", "Refill_Number", "Drug_Class", "Is_Controlled",
    "DEA_Schedule", "Copay",
]

DRUG_CLASSES = {
    "Oxycodone": "Opioid Analgesic",
    "Adderall": "CNS Stimulant",
    "Lorazepam": "Benzodiazepine",
    "Gabapentin": "Anticonvulsant",
    "Lisinopril": "ACE Inhibitor",
    "Humira": "Immunosuppressant",
    "Lipitor": "Statin",
    "Metformin": "Antidiabetic",
    "Advair": "Bronchodilator",
    "Insulin": "Antidiabetic",
}


def generate_normal_pharmacy_claim(claim_id):
    member = random.choice(PHARMA_MEMBER_IDS[1:])  # Skip fraud member
    prescriber = random.choice(PRESCRIBER_NPIS[1:])  # Skip pill mill
    pharmacy = random.choice(PHARMACY_NPIS)
    fill_date = random_date()
    ndc = random.choice(list(NDC_CATALOG.keys()))
    drug_name, is_controlled, dea_sched, price_low, price_high, is_generic = NDC_CATALOG[ndc]
    drug_class = DRUG_CLASSES[drug_name]
    billed = money(random.uniform(price_low, price_high))
    allowed = money(billed * random.uniform(0.70, 0.90))
    paid = money(allowed * random.uniform(0.80, 0.95))
    quantity = random.choice([30, 60, 90])
    days_supply = random.choice([30, 60, 90])
    refill_number = random.randint(0, 5)
    copay = money(random.choice([5, 10, 15, 20, 25, 30, 35, 40, 50]))
    return [
        f"RX-{claim_id:06d}", member, prescriber, pharmacy, fmt_date(fill_date),
        ndc, drug_name, billed, allowed, paid, quantity, days_supply,
        refill_number, drug_class, is_controlled, dea_sched, copay,
    ]


# ---------------------------------------------------------------------------
# Pharmacy fraud pattern generators
# ---------------------------------------------------------------------------

def generate_doctor_shopping_claims(start_id):
    """FRAUD 1: Member MBR-90001 gets controlled substances from 5+ prescribers."""
    rows = []
    member = PHARMA_MEMBER_DOCTOR_SHOPPER
    # Use at least 6 different prescribers (skip the pill mill to keep patterns separate)
    prescribers_for_shopping = random.sample(PRESCRIBER_NPIS[1:], min(6, len(PRESCRIBER_NPIS) - 1))
    for i in range(18):
        claim_id = start_id + i
        prescriber = prescribers_for_shopping[i % len(prescribers_for_shopping)]
        pharmacy = random.choice(PHARMACY_NPIS)
        fill_date = random_date()
        ndc = random.choice(CONTROLLED_NDCS)
        drug_name, is_controlled, dea_sched, price_low, price_high, is_generic = NDC_CATALOG[ndc]
        drug_class = DRUG_CLASSES[drug_name]
        billed = money(random.uniform(price_low, price_high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        quantity = random.choice([60, 90, 120])
        days_supply = 30
        refill_number = random.randint(0, 3)
        copay = money(random.choice([10, 15, 20]))
        rows.append([
            f"RX-{claim_id:06d}", member, prescriber, pharmacy, fmt_date(fill_date),
            ndc, drug_name, billed, allowed, paid, quantity, days_supply,
            refill_number, drug_class, is_controlled, dea_sched, copay,
        ])
    return rows


def generate_pill_mill_claims(start_id):
    """FRAUD 2: Prescriber 1987654001 writes 65 claims, mostly controlled, high quantity."""
    rows = []
    prescriber = PRESCRIBER_NPIS_PILL_MILL
    for i in range(65):
        claim_id = start_id + i
        member = random.choice(PHARMA_MEMBER_IDS[1:])
        pharmacy = random.choice(PHARMACY_NPIS)
        fill_date = random_date()
        # Mostly controlled (55 of 65)
        if i < 55:
            ndc = random.choice(CONTROLLED_NDCS)
        else:
            ndc = random.choice(NON_CONTROLLED_NDCS)
        drug_name, is_controlled, dea_sched, price_low, price_high, is_generic = NDC_CATALOG[ndc]
        drug_class = DRUG_CLASSES[drug_name]
        billed = money(random.uniform(price_low, price_high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        # High quantities for controlled substances
        if is_controlled:
            quantity = random.choice([180, 240, 270, 360])
        else:
            quantity = random.choice([60, 90])
        days_supply = 30
        refill_number = random.randint(0, 6)
        copay = money(random.choice([10, 15, 20]))
        rows.append([
            f"RX-{claim_id:06d}", member, prescriber, pharmacy, fmt_date(fill_date),
            ndc, drug_name, billed, allowed, paid, quantity, days_supply,
            refill_number, drug_class, is_controlled, dea_sched, copay,
        ])
    return rows


def generate_early_refill_claims(start_id):
    """FRAUD 3: 20 claims where same member+drug has refills 10-15 days apart."""
    rows = []
    # Create 10 pairs (20 claims)
    for i in range(10):
        member = random.choice(PHARMA_MEMBER_IDS[1:])
        prescriber = random.choice(PRESCRIBER_NPIS[1:])
        pharmacy = random.choice(PHARMACY_NPIS)
        ndc = random.choice(list(NDC_CATALOG.keys()))
        drug_name, is_controlled, dea_sched, price_low, price_high, is_generic = NDC_CATALOG[ndc]
        drug_class = DRUG_CLASSES[drug_name]

        # First fill
        fill_date1 = random_date()
        billed = money(random.uniform(price_low, price_high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        quantity = 30
        days_supply = 30
        copay = money(random.choice([10, 15, 20, 25]))
        rows.append([
            f"RX-{start_id + 2 * i:06d}", member, prescriber, pharmacy,
            fmt_date(fill_date1), ndc, drug_name, billed, allowed, paid,
            quantity, days_supply, i, drug_class, is_controlled, dea_sched, copay,
        ])

        # Second fill – only 10-15 days later (should be 30)
        gap = random.randint(10, 15)
        fill_date2 = fill_date1 + timedelta(days=gap)
        billed2 = money(random.uniform(price_low, price_high))
        allowed2 = money(billed2 * random.uniform(0.70, 0.90))
        paid2 = money(allowed2 * random.uniform(0.80, 0.95))
        rows.append([
            f"RX-{start_id + 2 * i + 1:06d}", member, prescriber, pharmacy,
            fmt_date(fill_date2), ndc, drug_name, billed2, allowed2, paid2,
            quantity, days_supply, i + 1, drug_class, is_controlled, dea_sched, copay,
        ])
    return rows


def generate_excessive_quantity_claims(start_id):
    """FRAUD 4: 10 claims with quantity > 360 and days_supply 30."""
    rows = []
    for i in range(10):
        member = random.choice(PHARMA_MEMBER_IDS[1:])
        prescriber = random.choice(PRESCRIBER_NPIS[1:])
        pharmacy = random.choice(PHARMACY_NPIS)
        fill_date = random_date()
        ndc = random.choice(list(NDC_CATALOG.keys()))
        drug_name, is_controlled, dea_sched, price_low, price_high, is_generic = NDC_CATALOG[ndc]
        drug_class = DRUG_CLASSES[drug_name]
        billed = money(random.uniform(price_low, price_high))
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        quantity = random.choice([400, 450, 500, 540, 600, 720])
        days_supply = 30
        refill_number = random.randint(0, 3)
        copay = money(random.choice([10, 15, 20]))
        rows.append([
            f"RX-{start_id + i:06d}", member, prescriber, pharmacy,
            fmt_date(fill_date), ndc, drug_name, billed, allowed, paid,
            quantity, days_supply, refill_number, drug_class, is_controlled,
            dea_sched, copay,
        ])
    return rows


def generate_high_cost_generic_claims(start_id):
    """FRAUD 5: 15 claims for generic drugs with Amount_Billed > $2000."""
    rows = []
    for i in range(15):
        member = random.choice(PHARMA_MEMBER_IDS[1:])
        prescriber = random.choice(PRESCRIBER_NPIS[1:])
        pharmacy = random.choice(PHARMACY_NPIS)
        fill_date = random_date()
        ndc = random.choice(GENERIC_NDCS)
        drug_name, is_controlled, dea_sched, _plow, _phigh, is_generic = NDC_CATALOG[ndc]
        drug_class = DRUG_CLASSES[drug_name]
        billed = money(random.uniform(2100, 5000))  # Way too high for a generic
        allowed = money(billed * random.uniform(0.70, 0.90))
        paid = money(allowed * random.uniform(0.80, 0.95))
        quantity = random.choice([30, 60, 90])
        days_supply = random.choice([30, 60, 90])
        refill_number = random.randint(0, 4)
        copay = money(random.choice([10, 15, 20, 25]))
        rows.append([
            f"RX-{start_id + i:06d}", member, prescriber, pharmacy,
            fmt_date(fill_date), ndc, drug_name, billed, allowed, paid,
            quantity, days_supply, refill_number, drug_class, is_controlled,
            dea_sched, copay,
        ])
    return rows


# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def generate_medical_csv():
    """Generate 500 medical claims with embedded fraud patterns."""
    all_rows = []
    claim_counter = 1

    # FRAUD 1: Upcoding – 50 claims
    fraud_rows = generate_upcoding_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 2: Duplicate billing – 30 claims (15 pairs)
    fraud_rows = generate_duplicate_billing_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 3: High billing – 10 claims
    fraud_rows = generate_high_billing_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 4: Weekend billing – 25 claims
    fraud_rows = generate_weekend_billing_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 5: Future dates – 5 claims
    fraud_rows = generate_future_date_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # Fill remaining with normal claims to reach 500
    fraud_count = len(all_rows)
    normal_needed = 500 - fraud_count
    for i in range(normal_needed):
        row = generate_normal_medical_claim(claim_counter + i)
        all_rows.append(row)

    # Shuffle so fraud rows aren't all at the top
    random.shuffle(all_rows)

    with open(MEDICAL_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(MEDICAL_HEADERS)
        writer.writerows(all_rows)

    print(f"Medical claims CSV written: {MEDICAL_CSV}")
    print(f"  Total rows: {len(all_rows)}")
    print(f"  Fraud rows: {fraud_count}")
    print(f"  Normal rows: {normal_needed}")


def generate_pharmacy_csv():
    """Generate 500 pharmacy claims with embedded fraud patterns."""
    all_rows = []
    claim_counter = 1

    # FRAUD 1: Doctor shopping – 18 claims
    fraud_rows = generate_doctor_shopping_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 2: Pill mill – 65 claims
    fraud_rows = generate_pill_mill_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 3: Early refills – 20 claims (10 pairs)
    fraud_rows = generate_early_refill_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 4: Excessive quantity – 10 claims
    fraud_rows = generate_excessive_quantity_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # FRAUD 5: High-cost generics – 15 claims
    fraud_rows = generate_high_cost_generic_claims(claim_counter)
    all_rows.extend(fraud_rows)
    claim_counter += len(fraud_rows)

    # Fill remaining with normal claims to reach 500
    fraud_count = len(all_rows)
    normal_needed = 500 - fraud_count
    for i in range(normal_needed):
        row = generate_normal_pharmacy_claim(claim_counter + i)
        all_rows.append(row)

    # Shuffle so fraud rows aren't all at the top
    random.shuffle(all_rows)

    with open(PHARMACY_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(PHARMACY_HEADERS)
        writer.writerows(all_rows)

    print(f"Pharmacy claims CSV written: {PHARMACY_CSV}")
    print(f"  Total rows: {len(all_rows)}")
    print(f"  Fraud rows: {fraud_count}")
    print(f"  Normal rows: {normal_needed}")


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print("Generating sample FWA claims data...\n")
    generate_medical_csv()
    print()
    generate_pharmacy_csv()
    print("\nDone! Files generated in:", OUTPUT_DIR)
