"""Seed 2000 members with realistic demographics. Some members are tagged for fraud scenarios."""

from datetime import date, timedelta

MEMBER_FIRST_NAMES_M = [
    "James", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony",
    "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
]

MEMBER_FIRST_NAMES_F = [
    "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
    "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
    "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly", "Emily", "Donna",
]

MEMBER_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Patel", "Shah", "Chen", "Kumar", "Singh",
    "Morgan", "Cooper", "Reed", "Bailey", "Bell", "Murphy", "Barnes",
]

STATES = ["TX", "CA", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI"]
PLAN_TYPES = ["MA", "MA", "MA", "Commercial", "Commercial", "Medicaid"]
PLAN_IDS = {
    "MA": ["MA-HMO-001", "MA-PPO-002", "MA-PFFS-003"],
    "Commercial": ["COM-HMO-010", "COM-PPO-020"],
    "Medicaid": ["MCD-001"],
}

# ─── Bad actor members (tagged for pharmacy fraud scenarios) ───
# Indices 0-9: P2 Doctor shopping (visit many prescribers for controlled substances)
# Indices 10-17: P3 Pharmacy shopping (fill same drug at many pharmacies)
# Indices 18-27: P4 Early refill (refill before supply runs out)
# Indices 28-37: P10 Stockpiling (accumulate excess supply)
# Indices 38-52: P12 Phantom members (eligibility expired)
# Indices 53-72: P6 Phantom claims (no medical claims, only pharmacy)
# Indices 73-82: M7 Provider collusion (shared patients)

BAD_MEMBER_CONFIGS = {}
for i in range(10):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "P2_doctor_shopping"}
for i in range(10, 18):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "P3_pharmacy_shopping"}
for i in range(18, 28):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "P4_early_refill"}
for i in range(28, 38):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "P10_stockpiling"}
for i in range(38, 53):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "P12_phantom_member", "eligibility_expired": True}
for i in range(53, 73):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "P6_phantom_rx_only"}
for i in range(73, 83):
    BAD_MEMBER_CONFIGS[i] = {"fraud_tag": "M7_collusion_patient"}


def generate_members(rng, ref_date: date | None = None) -> list[dict]:
    """Generate 2000 members."""
    if ref_date is None:
        ref_date = date(2025, 10, 31)

    members = []
    for i in range(2000):
        gender = rng.choice(["M", "F"])
        if gender == "M":
            first = rng.choice(MEMBER_FIRST_NAMES_M)
        else:
            first = rng.choice(MEMBER_FIRST_NAMES_F)
        last = rng.choice(MEMBER_LAST_NAMES)
        state = rng.choice(STATES)

        # Age distribution: 0-17 (10%), 18-44 (25%), 45-64 (30%), 65+ (35%)
        age_bucket = rng.random()
        if age_bucket < 0.10:
            age = rng.randint(1, 17)
        elif age_bucket < 0.35:
            age = rng.randint(18, 44)
        elif age_bucket < 0.65:
            age = rng.randint(45, 64)
        else:
            age = rng.randint(65, 95)

        dob = date(ref_date.year - age, rng.randint(1, 12), rng.randint(1, 28))
        plan_type = rng.choice(PLAN_TYPES)
        if age >= 65:
            plan_type = "MA"  # Medicare Advantage for 65+

        config = BAD_MEMBER_CONFIGS.get(i, {})

        # Eligibility
        elig_start = dob.replace(year=ref_date.year - rng.randint(1, 5))
        if elig_start > ref_date:
            elig_start = ref_date - timedelta(days=365)

        elig_end = None
        if config.get("eligibility_expired"):
            # Expired 1-6 months ago
            elig_end = ref_date - timedelta(days=rng.randint(30, 180))

        members.append({
            "member_id": f"MBR-{100001 + i:06d}",
            "first_name": first,
            "last_name": last,
            "date_of_birth": dob,
            "gender": gender,
            "address": f"{rng.randint(100, 9999)} {rng.choice(['Oak', 'Elm', 'Maple', 'Cedar', 'Pine'])} {rng.choice(['St', 'Ave', 'Dr', 'Ln', 'Ct'])}",
            "city": rng.choice(["Houston", "Dallas", "Miami", "Chicago", "Phoenix", "Philadelphia", "San Antonio", "Los Angeles", "New York", "Atlanta"]),
            "state": state,
            "zip_code": f"{rng.randint(10000, 99999)}",
            "plan_id": rng.choice(PLAN_IDS[plan_type]),
            "plan_type": plan_type,
            "eligibility_start": elig_start,
            "eligibility_end": elig_end,
            "is_active": elig_end is None,
            "_fraud_tag": config.get("fraud_tag"),
            "_index": i,
            "_age": age,
            "_gender": gender,
        })
    return members
