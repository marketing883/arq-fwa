"""Seed providers and pharmacies with realistic data, including flagged bad actors."""

SPECIALTIES = [
    "Family Medicine", "Internal Medicine", "Cardiology", "Orthopedic Surgery",
    "Dermatology", "Psychiatry", "Neurology", "Gastroenterology",
    "Pulmonology", "Endocrinology", "Oncology", "General Surgery",
    "Emergency Medicine", "Radiology", "Pathology", "Physical Therapy",
    "Pain Management", "Urology", "Ophthalmology", "OB/GYN",
]

STATES = ["TX", "CA", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI"]
CITIES = {
    "TX": ["Houston", "Dallas", "Austin", "San Antonio"],
    "CA": ["Los Angeles", "San Francisco", "San Diego", "Sacramento"],
    "FL": ["Miami", "Orlando", "Tampa", "Jacksonville"],
    "NY": ["New York", "Buffalo", "Albany", "Rochester"],
    "IL": ["Chicago", "Springfield", "Naperville", "Peoria"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Harrisburg"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo"],
    "GA": ["Atlanta", "Savannah", "Augusta", "Macon"],
    "NC": ["Charlotte", "Raleigh", "Durham", "Greensboro"],
    "MI": ["Detroit", "Grand Rapids", "Ann Arbor", "Lansing"],
}

FIRST_NAMES = [
    "James", "Robert", "Michael", "David", "William", "John", "Richard",
    "Maria", "Jennifer", "Patricia", "Linda", "Sarah", "Emily", "Jessica",
    "Thomas", "Christopher", "Daniel", "Andrew", "Karen", "Lisa",
    "Steven", "Paul", "Mark", "Kevin", "Susan", "Nancy", "Angela", "Amy",
    "Brian", "George", "Joseph", "Charles", "Barbara", "Elizabeth", "Dorothy",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Patel", "Shah", "Chen", "Kumar", "Singh",
]

# ─── Bad actor providers (flagged for fraud scenarios) ───
# Provider indices (0-based) that will be bad actors:
# Indices 0-4: M1 Upcoding (consistently bill highest E&M)
# Indices 5-7: M2 Unbundling (labs)
# Indices 8-11: M3 Duplicate billing
# Index 12-13: M4 Phantom billing (ghost providers)
# Index 14-16: M5 Kickback referral (referring provider)
# Index 17-19: M5 Kickback receiving lab
# Index 20-22: M8 Modifier misuse
# Index 23-24: M9 Copay waiver
# Index 25-26: M10 Inpatient/outpatient misclassification
# Index 27: M11 DME fraud supplier
# Index 28-30: M12 Lab abuse (always order labs)
# Index 31-32: M13 Ghost providers (inactive/OIG)
# Index 33: M14 Double dipping
# Index 34-35: M15 Telehealth volume
# Index 36-37: M16 Chart padding
# Index 38-40: P5 Controlled substance diversion prescribers
# Index 41-43: P8 Kickback to specific pharmacy
# Index 44-45: P9 Invalid prescriber (no DEA)

BAD_ACTOR_CONFIGS = {
    # M1: Upcoding providers
    0: {"fraud_tag": "M1_upcoding", "specialty": "Family Medicine"},
    1: {"fraud_tag": "M1_upcoding", "specialty": "Internal Medicine"},
    2: {"fraud_tag": "M1_upcoding", "specialty": "Cardiology"},
    3: {"fraud_tag": "M1_upcoding", "specialty": "Pain Management"},
    4: {"fraud_tag": "M1_upcoding", "specialty": "Endocrinology"},
    # M2: Unbundling labs
    5: {"fraud_tag": "M2_unbundling", "specialty": "Pathology"},
    6: {"fraud_tag": "M2_unbundling", "specialty": "Internal Medicine"},
    7: {"fraud_tag": "M2_unbundling", "specialty": "Pathology"},
    # M3: Duplicate billing
    8: {"fraud_tag": "M3_duplicate", "specialty": "General Surgery"},
    9: {"fraud_tag": "M3_duplicate", "specialty": "Orthopedic Surgery"},
    10: {"fraud_tag": "M3_duplicate", "specialty": "Radiology"},
    11: {"fraud_tag": "M3_duplicate", "specialty": "Cardiology"},
    # M4: Phantom billing
    12: {"fraud_tag": "M4_phantom", "specialty": "Internal Medicine"},
    13: {"fraud_tag": "M4_phantom", "specialty": "Family Medicine"},
    # M5: Kickback — referrers
    14: {"fraud_tag": "M5_kickback_referrer", "specialty": "Family Medicine"},
    15: {"fraud_tag": "M5_kickback_referrer", "specialty": "Internal Medicine"},
    16: {"fraud_tag": "M5_kickback_referrer", "specialty": "Pain Management"},
    # M5: Kickback — receiving labs/imaging
    17: {"fraud_tag": "M5_kickback_receiver", "specialty": "Pathology", "entity_type": "organization"},
    18: {"fraud_tag": "M5_kickback_receiver", "specialty": "Radiology", "entity_type": "organization"},
    19: {"fraud_tag": "M5_kickback_receiver", "specialty": "Pathology", "entity_type": "organization"},
    # M8: Modifier misuse
    20: {"fraud_tag": "M8_modifier", "specialty": "Dermatology"},
    21: {"fraud_tag": "M8_modifier", "specialty": "Family Medicine"},
    22: {"fraud_tag": "M8_modifier", "specialty": "Internal Medicine"},
    # M9: Copay waiver
    23: {"fraud_tag": "M9_copay_waiver", "specialty": "Physical Therapy"},
    24: {"fraud_tag": "M9_copay_waiver", "specialty": "Dermatology"},
    # M10: IP/OP misclass
    25: {"fraud_tag": "M10_misclass", "specialty": "General Surgery", "entity_type": "organization"},
    26: {"fraud_tag": "M10_misclass", "specialty": "Orthopedic Surgery", "entity_type": "organization"},
    # M11: DME fraud
    27: {"fraud_tag": "M11_dme", "specialty": "Physical Therapy", "entity_type": "organization"},
    # M12: Lab abuse
    28: {"fraud_tag": "M12_lab_abuse", "specialty": "Internal Medicine"},
    29: {"fraud_tag": "M12_lab_abuse", "specialty": "Family Medicine"},
    30: {"fraud_tag": "M12_lab_abuse", "specialty": "Endocrinology"},
    # M13: Ghosting (inactive / OIG excluded)
    31: {"fraud_tag": "M13_ghost", "specialty": "Family Medicine", "is_active": False},
    32: {"fraud_tag": "M13_ghost", "specialty": "Pain Management", "oig_excluded": True},
    # M14: Double dipping
    33: {"fraud_tag": "M14_double_dip", "specialty": "Orthopedic Surgery"},
    # M15: Telehealth volume
    34: {"fraud_tag": "M15_telehealth", "specialty": "Psychiatry"},
    35: {"fraud_tag": "M15_telehealth", "specialty": "Family Medicine"},
    # M16: Chart padding
    36: {"fraud_tag": "M16_chart_padding", "specialty": "Internal Medicine"},
    37: {"fraud_tag": "M16_chart_padding", "specialty": "Family Medicine"},
    # P5: Controlled substance diversion prescribers
    38: {"fraud_tag": "P5_diversion", "specialty": "Pain Management", "dea_registration": "AP1234567", "dea_schedule": "CII"},
    39: {"fraud_tag": "P5_diversion", "specialty": "Family Medicine", "dea_registration": "BM2345678", "dea_schedule": "CII"},
    40: {"fraud_tag": "P5_diversion", "specialty": "Internal Medicine", "dea_registration": "FC3456789", "dea_schedule": "CII"},
    # P8: Kickback to pharmacy
    41: {"fraud_tag": "P8_kickback", "specialty": "Family Medicine", "dea_registration": "BM4567890", "dea_schedule": "CII"},
    42: {"fraud_tag": "P8_kickback", "specialty": "Pain Management", "dea_registration": "AP5678901", "dea_schedule": "CII"},
    43: {"fraud_tag": "P8_kickback", "specialty": "Internal Medicine", "dea_registration": "FC6789012", "dea_schedule": "CII"},
    # P9: Invalid prescriber (no DEA but prescribes controlled)
    44: {"fraud_tag": "P9_invalid_prescriber", "specialty": "Family Medicine", "dea_registration": None, "dea_schedule": None},
    45: {"fraud_tag": "P9_invalid_prescriber", "specialty": "Internal Medicine", "dea_registration": None, "dea_schedule": None},
}

# ─── Pharmacy data ───
PHARMACY_CHAINS = ["CVS", "Walgreens", "Rite Aid", "Walmart", "Kroger", None, None]
PHARMACY_TYPES = ["retail", "retail", "retail", "retail", "mail_order", "specialty", "compounding"]

# Bad actor pharmacies:
# Index 0: P6 phantom claims pharmacy
# Index 1-2: P7 high-cost substitution
# Index 3-5: P8 kickback receiving pharmacy
# Index 6: P11 compound drug fraud
# Index 7-8: P13 collusion with specific providers

BAD_PHARMACY_CONFIGS = {
    0: {"fraud_tag": "P6_phantom", "pharmacy_type": "retail"},
    1: {"fraud_tag": "P7_substitution", "pharmacy_type": "retail"},
    2: {"fraud_tag": "P7_substitution", "pharmacy_type": "retail"},
    3: {"fraud_tag": "P8_kickback_rx", "pharmacy_type": "retail"},
    4: {"fraud_tag": "P8_kickback_rx", "pharmacy_type": "retail"},
    5: {"fraud_tag": "P8_kickback_rx", "pharmacy_type": "retail"},
    6: {"fraud_tag": "P11_compound", "pharmacy_type": "compounding"},
    7: {"fraud_tag": "P13_collusion", "pharmacy_type": "retail"},
    8: {"fraud_tag": "P13_collusion", "pharmacy_type": "retail"},
}


def generate_npi(index: int) -> str:
    """Generate a realistic-looking NPI."""
    return f"1{index + 100000000:09d}"


def generate_providers(rng) -> list[dict]:
    """Generate 200 providers."""
    providers = []
    for i in range(200):
        state = rng.choice(STATES)
        city = rng.choice(CITIES[state])
        first = rng.choice(FIRST_NAMES)
        last = rng.choice(LAST_NAMES)

        config = BAD_ACTOR_CONFIGS.get(i, {})
        specialty = config.get("specialty", rng.choice(SPECIALTIES))
        entity_type = config.get("entity_type", "individual")

        if entity_type == "organization":
            name = f"{last} {specialty} Associates"
        else:
            name = f"Dr. {first} {last}"

        # Most prescribers have DEA unless explicitly removed
        dea_reg = config.get("dea_registration", f"A{rng.choice(['P','M','B','F'])}{rng.randint(1000000, 9999999)}")
        dea_sched = config.get("dea_schedule", "CII")
        if "dea_registration" in config and config["dea_registration"] is None:
            dea_reg = None
            dea_sched = None

        providers.append({
            "npi": generate_npi(i),
            "name": name,
            "specialty": specialty,
            "taxonomy_code": f"207{rng.choice('QRXLPNVWY')}{rng.choice('ABCDE')}0000X",
            "practice_address": f"{rng.randint(100, 9999)} {rng.choice(['Main', 'Oak', 'Elm', 'Medical Center', 'Healthcare'])} {rng.choice(['St', 'Ave', 'Blvd', 'Dr'])}",
            "practice_city": city,
            "practice_state": state,
            "practice_zip": f"{rng.randint(10000, 99999)}",
            "phone": f"{rng.randint(200, 999)}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
            "entity_type": entity_type,
            "is_active": config.get("is_active", True),
            "oig_excluded": config.get("oig_excluded", False),
            "dea_registration": dea_reg,
            "dea_schedule": dea_sched,
            "_fraud_tag": config.get("fraud_tag"),
            "_index": i,
        })
    return providers


def generate_pharmacies(rng) -> list[dict]:
    """Generate 50 pharmacies."""
    pharmacies = []
    for i in range(50):
        state = rng.choice(STATES)
        city = rng.choice(CITIES[state])
        config = BAD_PHARMACY_CONFIGS.get(i, {})
        chain = rng.choice(PHARMACY_CHAINS)
        ptype = config.get("pharmacy_type", rng.choice(PHARMACY_TYPES))

        if chain:
            name = f"{chain} Pharmacy #{rng.randint(1000, 9999)}"
        else:
            name = f"{rng.choice(LAST_NAMES)} {rng.choice(['Pharmacy', 'Drug Store', 'Rx Center', 'Apothecary'])}"

        pharmacies.append({
            "npi": f"3{i + 100000000:09d}",
            "name": name,
            "chain_name": chain,
            "address": f"{rng.randint(100, 9999)} {rng.choice(['Main', 'Commerce', 'Market'])} {rng.choice(['St', 'Ave', 'Blvd'])}",
            "city": city,
            "state": state,
            "zip_code": f"{rng.randint(10000, 99999)}",
            "phone": f"{rng.randint(200, 999)}-{rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
            "pharmacy_type": ptype,
            "is_active": True,
            "oig_excluded": False,
            "_fraud_tag": config.get("fraud_tag"),
            "_index": i,
        })
    return pharmacies
