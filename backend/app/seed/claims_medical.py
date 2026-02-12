"""Generate ~15,000 synthetic medical claims with fraud scenarios injected for rules M1-M16.

Exports ``generate_medical_claims(rng, providers, members, cpt_codes, icd_codes, ref_date)``
which returns a list of claim dicts ready for insertion into the ``medical_claims`` table.

Every claim dict includes all columns from the MedicalClaim model plus a private
``_fraud_tag`` field used for downstream verification.

The generator is fully deterministic: the same ``rng`` (``random.Random`` instance)
produces identical output across runs.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BATCH_ID = "SEED-BATCH-001"
STATUS = "processed"
CLAIM_PREFIX = "MCL-2025-"

PLACE_OFFICE = "11"
PLACE_INPATIENT = "21"
PLACE_ER = "23"
PLACE_TELEHEALTH = "02"

# BMP component codes (80048 unbundled)
BMP_COMPONENTS = ["82310", "82374", "82435", "82565", "82947", "84132", "84295", "84520"]

# E&M office visit CPTs (for normal distribution and several fraud rules)
EM_OFFICE_CODES = ["99211", "99212", "99213", "99214", "99215"]
EM_NEW_PATIENT_CODES = ["99201", "99202", "99203", "99204", "99205"]
EM_HOSPITAL_CODES = ["99221", "99222", "99223"]
EM_ER_CODES = ["99281", "99283", "99285"]
TELEHEALTH_CODES = ["99441", "99442", "99443"]

# Lab/diagnostic CPTs
LAB_CODES = [
    "80048", "80053", "85025", "83036", "80061", "84443", "81001",
]

# Commonly used outpatient procedure codes
OUTPATIENT_PROCEDURE_CODES = [
    "29881", "43239", "45380", "10060",
]

# Typical normal billing jitter: amount_billed = CMS * (1 + jitter)
NORMAL_JITTER_LOW = 0.90
NORMAL_JITTER_HIGH = 1.25

# How many months of claims history to generate
MONTHS_BACK = 12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _d(value: float) -> Decimal:
    """Convert float to Decimal rounded to 2 decimal places."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _next_claim_id(counter: list[int]) -> str:
    """Return the next sequential claim ID. *counter* is a single-element list used as mutable ref."""
    counter[0] += 1
    return f"{CLAIM_PREFIX}{counter[0]:06d}"


def _random_service_date(rng: random.Random, ref_date: date, months_back: int = MONTHS_BACK) -> date:
    """Pick a uniformly random service date in the window [ref_date - months_back months, ref_date]."""
    start = ref_date - timedelta(days=months_back * 30)
    delta = (ref_date - start).days
    return start + timedelta(days=rng.randint(0, delta))


def _pick_icd(rng: random.Random, icd_codes: list[dict], *, category: str | None = None) -> dict:
    """Pick a random ICD code, optionally filtered by category."""
    pool = icd_codes if category is None else [c for c in icd_codes if c["category"] == category]
    if not pool:
        pool = icd_codes
    return rng.choice(pool)


def _pick_cpt(rng: random.Random, cpt_lookup: dict[str, dict], code_list: list[str]) -> dict:
    """Pick a random CPT record from *code_list* that exists in the lookup."""
    valid = [c for c in code_list if c in cpt_lookup]
    if not valid:
        return rng.choice(list(cpt_lookup.values()))
    return cpt_lookup[rng.choice(valid)]


def _pick_secondary_dx(rng: random.Random, icd_codes: list[dict], primary_code: str, count: int) -> list[str | None]:
    """Return up to *count* secondary ICD codes (different from primary). Pads with None."""
    others = [c["icd_code"] for c in icd_codes if c["icd_code"] != primary_code]
    rng.shuffle(others)
    picked = others[:count]
    while len(picked) < 4:
        picked.append(None)
    return picked[:4]  # diagnosis_code_2 .. diagnosis_code_4 (index 0-2 used, index 3 spare)


def _provider_indices_for_tag(providers: list[dict], tag: str) -> list[int]:
    """Return provider list indices matching a given fraud tag."""
    return [i for i, p in enumerate(providers) if p.get("_fraud_tag") == tag]


def _member_indices_for_tag(members: list[dict], tag: str) -> list[int]:
    """Return member list indices matching a given fraud tag."""
    return [i for i, m in enumerate(members) if m.get("_fraud_tag") == tag]


def _normal_members(members: list[dict]) -> list[int]:
    """Return indices of members without any fraud tag."""
    return [i for i, m in enumerate(members) if m.get("_fraud_tag") is None]


def _normal_providers(providers: list[dict]) -> list[int]:
    """Return indices of providers without any fraud tag."""
    return [i for i, p in enumerate(providers) if p.get("_fraud_tag") is None]


def _build_claim(
    *,
    counter: list[int],
    member_idx: int,
    members: list[dict],
    provider_idx: int,
    providers: list[dict],
    service_date: date,
    place_of_service: str,
    cpt_code: str,
    cpt_modifier: str | None,
    dx_primary: str,
    dx_2: str | None,
    dx_3: str | None,
    dx_4: str | None,
    amount_billed: Decimal,
    amount_allowed: Decimal,
    amount_paid: Decimal,
    units: int,
    length_of_stay: int | None,
    drg_code: str | None,
    revenue_code: str | None,
    plan_id: str | None,
    referring_provider_idx: int | None,
    fraud_tag: str | None,
    claim_type: str = "professional",
) -> dict[str, Any]:
    """Construct a single claim dict."""
    member = members[member_idx]
    claim = {
        "claim_id": _next_claim_id(counter),
        "member_id": member_idx,
        "provider_id": provider_idx,
        "referring_provider_id": referring_provider_idx,
        "service_date": service_date,
        "admission_date": service_date if place_of_service == PLACE_INPATIENT else None,
        "discharge_date": (
            service_date + timedelta(days=length_of_stay)
            if place_of_service == PLACE_INPATIENT and length_of_stay is not None
            else None
        ),
        "place_of_service": place_of_service,
        "claim_type": claim_type,
        "cpt_code": cpt_code,
        "cpt_modifier": cpt_modifier,
        "diagnosis_code_primary": dx_primary,
        "diagnosis_code_2": dx_2,
        "diagnosis_code_3": dx_3,
        "diagnosis_code_4": dx_4,
        "amount_billed": amount_billed,
        "amount_allowed": amount_allowed,
        "amount_paid": amount_paid,
        "units": units,
        "length_of_stay": length_of_stay,
        "drg_code": drg_code,
        "revenue_code": revenue_code,
        "plan_id": plan_id or member.get("plan_id", "MA-HMO-001"),
        "status": STATUS,
        "batch_id": BATCH_ID,
        "_fraud_tag": fraud_tag,
    }
    return claim


# ---------------------------------------------------------------------------
# Individual fraud-scenario generators
# ---------------------------------------------------------------------------

def _gen_m1_upcoding(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M1 Upcoding: 5 providers always bill 99215 at $350+ (CMS expects ~$200).

    Produces ~200 claims.
    """
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M1_upcoding")
    per_provider = 40  # 5 * 40 = 200

    for pidx in prov_idxs:
        for _ in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            # Simple diagnosis — does not justify 99215
            icd = rng.choice([c for c in icd_codes if c["icd_code"] in ("E11.9", "I10", "J00", "J06.9", "Z00.00")])
            billed = _d(rng.uniform(350.0, 480.0))
            allowed = _d(200.0)  # CMS rate
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            sec = _pick_secondary_dx(rng, icd_codes, icd["icd_code"], rng.randint(0, 1))
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code="99215",
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=sec[0],
                dx_3=sec[1],
                dx_4=sec[2],
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M1_upcoding",
            ))
    return claims


def _gen_m2_unbundling(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M2 Unbundling: 3 providers split BMP (80048) into individual components.

    ~80 claim clusters (2-4 component claims each).
    """
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M2_unbundling")
    clusters_per = 27  # ceil(80/3)

    for pidx in prov_idxs:
        for _ in range(clusters_per):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            icd = rng.choice([c for c in icd_codes if c["icd_code"] in ("E11.9", "I10", "Z00.00")])
            # Pick 3-5 components
            n_components = rng.randint(3, 5)
            components = rng.sample(BMP_COMPONENTS, n_components)
            for comp_code in components:
                comp_cpt = cpt_lookup.get(comp_code)
                base_price = float(comp_cpt["non_facility_price"]) if comp_cpt else 8.0
                billed = _d(base_price * rng.uniform(1.0, 1.3))
                allowed = _d(base_price)
                paid = _d(float(allowed) * rng.uniform(0.80, 0.90))
                claims.append(_build_claim(
                    counter=counter,
                    member_idx=midx,
                    members=members,
                    provider_idx=pidx,
                    providers=providers,
                    service_date=svc_date,
                    place_of_service=PLACE_OFFICE,
                    cpt_code=comp_code,
                    cpt_modifier=None,
                    dx_primary=icd["icd_code"],
                    dx_2=None,
                    dx_3=None,
                    dx_4=None,
                    amount_billed=billed,
                    amount_allowed=allowed,
                    amount_paid=paid,
                    units=1,
                    length_of_stay=None,
                    drg_code=None,
                    revenue_code=None,
                    plan_id=None,
                    referring_provider_idx=None,
                    fraud_tag="M2_unbundling",
                ))
    return claims


def _gen_m3_duplicate(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M3 Duplicate billing: 4 providers submit ~100 duplicate pairs.

    Each pair has the same member+provider+CPT+date but different claim_ids.
    """
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M3_duplicate")
    pairs_per = 25  # 4 * 25 = 100

    for pidx in prov_idxs:
        for _ in range(pairs_per):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = rng.choice(EM_OFFICE_CODES + OUTPATIENT_PROCEDURE_CODES)
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 150.0
            billed = _d(base_price * rng.uniform(1.0, 1.20))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)
            sec = _pick_secondary_dx(rng, icd_codes, icd["icd_code"], rng.randint(0, 1))

            shared_kwargs: dict[str, Any] = dict(
                members=members,
                member_idx=midx,
                providers=providers,
                provider_idx=pidx,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=sec[0],
                dx_3=sec[1],
                dx_4=sec[2],
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M3_duplicate",
            )
            # First claim
            claims.append(_build_claim(counter=counter, **shared_kwargs))
            # Duplicate (different claim_id)
            claims.append(_build_claim(counter=counter, **shared_kwargs))
    return claims


def _gen_m4_phantom(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M4 Phantom billing: 2 providers with no corroborating evidence. ~60 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M4_phantom")
    per_provider = 30  # 2 * 30 = 60

    for pidx in prov_idxs:
        # Each phantom claim uses a unique member picked from a quiet pool
        for _ in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            # Dates are scattered and isolated
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = rng.choice(EM_OFFICE_CODES + ["97110", "97140"])
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 120.0
            billed = _d(base_price * rng.uniform(1.10, 1.50))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M4_phantom",
            ))
    return claims


def _gen_m5_kickback(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M5 Kickback/self-referral: 3 referrer->receiver pairs, >85% referral concentration.

    ~150 claims total.
    """
    claims: list[dict] = []
    referrer_idxs = _provider_indices_for_tag(providers, "M5_kickback_referrer")
    receiver_idxs = _provider_indices_for_tag(providers, "M5_kickback_receiver")
    per_referrer = 50  # 3 * 50 = 150

    for r_idx, (ref_pidx, recv_pidx) in enumerate(zip(referrer_idxs, receiver_idxs)):
        for claim_num in range(per_referrer):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)

            # ~90% of claims go to the paired receiver (for >85% concentration)
            if claim_num < int(per_referrer * 0.90):
                actual_receiver = recv_pidx
            else:
                # Small fraction to other providers
                actual_receiver = rng.choice([
                    i for i in range(len(providers))
                    if providers[i].get("_fraud_tag") != "M5_kickback_referrer"
                    and i != recv_pidx
                ])

            # The claim is billed by the receiving provider with referring set
            lab_cpt = rng.choice(LAB_CODES + ["73721", "74177", "71046"])
            cpt_rec = cpt_lookup.get(lab_cpt)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 50.0
            billed = _d(base_price * rng.uniform(1.0, 1.15))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.80, 0.90))
            icd = _pick_icd(rng, icd_codes)

            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=actual_receiver,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=lab_cpt,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=ref_pidx,
                fraud_tag="M5_kickback",
            ))
    return claims


def _gen_m7_collusion(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
) -> list[dict]:
    """M7 Provider collusion: Shared patients between colluding provider pairs.

    Uses M7_collusion_patient members. Produces ~40 claim pairs (80 claims total).
    """
    claims: list[dict] = []
    collusion_member_idxs = _member_indices_for_tag(members, "M7_collusion_patient")
    # Pick two pairs of normal providers to act as colluding pairs
    normal_pidxs = _normal_providers(providers)
    # Use first 4 normal providers as 2 pairs
    pair_a = (normal_pidxs[0], normal_pidxs[1])
    pair_b = (normal_pidxs[2], normal_pidxs[3])
    pairs = [pair_a, pair_b]

    for pair in pairs:
        prov_a, prov_b = pair
        for midx in collusion_member_idxs[:5]:  # 5 members per pair
            # 4 same-day encounters per member across the year
            for _ in range(4):
                svc_date = _random_service_date(rng, ref_date)
                icd = _pick_icd(rng, icd_codes)

                # Provider A bills an E&M visit
                cpt_a = rng.choice(["99213", "99214"])
                rec_a = cpt_lookup.get(cpt_a)
                price_a = float(rec_a["non_facility_price"]) if rec_a else 120.0
                billed_a = _d(price_a * rng.uniform(1.0, 1.15))
                allowed_a = _d(price_a)
                paid_a = _d(float(allowed_a) * 0.80)

                claims.append(_build_claim(
                    counter=counter,
                    member_idx=midx,
                    members=members,
                    provider_idx=prov_a,
                    providers=providers,
                    service_date=svc_date,
                    place_of_service=PLACE_OFFICE,
                    cpt_code=cpt_a,
                    cpt_modifier=None,
                    dx_primary=icd["icd_code"],
                    dx_2=None,
                    dx_3=None,
                    dx_4=None,
                    amount_billed=billed_a,
                    amount_allowed=allowed_a,
                    amount_paid=paid_a,
                    units=1,
                    length_of_stay=None,
                    drg_code=None,
                    revenue_code=None,
                    plan_id=None,
                    referring_provider_idx=None,
                    fraud_tag="M7_collusion",
                ))

                # Provider B bills a complementary service same day
                cpt_b = rng.choice(["97110", "97140", "73721"])
                rec_b = cpt_lookup.get(cpt_b)
                price_b = float(rec_b["non_facility_price"]) if rec_b else 55.0
                billed_b = _d(price_b * rng.uniform(1.0, 1.15))
                allowed_b = _d(price_b)
                paid_b = _d(float(allowed_b) * 0.80)

                claims.append(_build_claim(
                    counter=counter,
                    member_idx=midx,
                    members=members,
                    provider_idx=prov_b,
                    providers=providers,
                    service_date=svc_date,
                    place_of_service=PLACE_OFFICE,
                    cpt_code=cpt_b,
                    cpt_modifier=None,
                    dx_primary=icd["icd_code"],
                    dx_2=None,
                    dx_3=None,
                    dx_4=None,
                    amount_billed=billed_b,
                    amount_allowed=allowed_b,
                    amount_paid=paid_b,
                    units=1,
                    length_of_stay=None,
                    drg_code=None,
                    revenue_code=None,
                    plan_id=None,
                    referring_provider_idx=None,
                    fraud_tag="M7_collusion",
                ))
    return claims


def _gen_m8_modifier(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M8 Modifier misuse: 3 providers use modifier 25 or 59 on >80% of claims. ~120 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M8_modifier")
    per_provider = 40  # 3 * 40 = 120

    for pidx in prov_idxs:
        modifier_of_choice = rng.choice(["25", "59"])
        for claim_num in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            # >85% have the modifier
            use_modifier = claim_num < int(per_provider * 0.85)
            cpt_code = rng.choice(EM_OFFICE_CODES)
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 120.0
            # Modifier adds ~20% billing bump
            price_mult = 1.20 if use_modifier else 1.0
            billed = _d(base_price * price_mult * rng.uniform(1.0, 1.10))
            allowed = _d(base_price * price_mult)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)
            sec = _pick_secondary_dx(rng, icd_codes, icd["icd_code"], rng.randint(0, 1))
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=modifier_of_choice if use_modifier else None,
                dx_primary=icd["icd_code"],
                dx_2=sec[0],
                dx_3=sec[1],
                dx_4=sec[2],
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M8_modifier",
            ))
    return claims


def _gen_m9_copay_waiver(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M9 Copay waiver: 2 providers have amount_billed == amount_allowed on 95%+ claims. ~180 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M9_copay_waiver")
    per_provider = 90  # 2 * 90 = 180

    for pidx in prov_idxs:
        for claim_num in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = rng.choice(EM_OFFICE_CODES + ["97110", "97140"])
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 100.0
            allowed = _d(base_price)
            # 96% of claims: billed == allowed (copay waiver pattern)
            is_waiver = claim_num < int(per_provider * 0.96)
            if is_waiver:
                billed = allowed
            else:
                billed = _d(float(allowed) * rng.uniform(1.10, 1.25))
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M9_copay_waiver",
            ))
    return claims


def _gen_m10_misclass(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M10 IP/OP misclassification: 2 facilities bill inpatient (POS=21, LOS 0-1) for outpatient procedures. ~50 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M10_misclass")
    per_provider = 25  # 2 * 25 = 50

    outpatient_cpts = OUTPATIENT_PROCEDURE_CODES + ["45380", "43239", "29881"]

    for pidx in prov_idxs:
        for _ in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = rng.choice(outpatient_cpts)
            cpt_rec = cpt_lookup.get(cpt_code)
            # Bill at inpatient rate (higher)
            base_price = float(cpt_rec["facility_price"]) if cpt_rec else 500.0
            inpatient_markup = rng.uniform(1.3, 2.0)
            billed = _d(base_price * inpatient_markup)
            allowed = _d(base_price * 1.2)
            paid = _d(float(allowed) * rng.uniform(0.80, 0.90))
            icd = _pick_icd(rng, icd_codes, category="Musculoskeletal")
            los = rng.choice([0, 0, 1, 1])  # Short stay
            drg = rng.choice(["470", "473", "743"])  # Common DRGs

            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_INPATIENT,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=los,
                drg_code=drg,
                revenue_code="0120",
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M10_misclass",
                claim_type="institutional",
            ))
    return claims


def _gen_m11_dme(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M11 DME fraud: 1 DME supplier bills K0856 (power wheelchair) for mobile patients. ~30 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M11_dme")

    for pidx in prov_idxs:
        for _ in range(30):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = "K0856"
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 5500.0
            billed = _d(base_price * rng.uniform(1.0, 1.15))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            # Diagnosis does not support wheelchair need
            icd = rng.choice([
                c for c in icd_codes
                if c["icd_code"] in ("M54.5", "I10", "E11.9", "Z00.00")
            ])
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M11_dme",
            ))
    return claims


def _gen_m12_lab_abuse(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M12 Lab/diagnostic abuse: 3 providers order labs on >90% of visits. ~200 claims.

    For each provider we generate paired E&M + lab claims so that the lab rate is >90%.
    """
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M12_lab_abuse")
    visits_per_provider = 34  # Each produces ~2 claims; 3 * 34 * 2 ~= 200

    for pidx in prov_idxs:
        for visit_num in range(visits_per_provider):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            icd = _pick_icd(rng, icd_codes)

            # E&M visit
            em_code = rng.choice(EM_OFFICE_CODES)
            rec_em = cpt_lookup.get(em_code)
            price_em = float(rec_em["non_facility_price"]) if rec_em else 120.0
            billed_em = _d(price_em * rng.uniform(1.0, 1.15))
            allowed_em = _d(price_em)
            paid_em = _d(float(allowed_em) * 0.80)

            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=em_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed_em,
                amount_allowed=allowed_em,
                amount_paid=paid_em,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M12_lab_abuse",
            ))

            # >92% of visits include a lab order
            if visit_num < int(visits_per_provider * 0.92):
                lab_code = rng.choice(LAB_CODES)
                rec_lab = cpt_lookup.get(lab_code)
                price_lab = float(rec_lab["non_facility_price"]) if rec_lab else 18.0
                billed_lab = _d(price_lab * rng.uniform(1.0, 1.10))
                allowed_lab = _d(price_lab)
                paid_lab = _d(float(allowed_lab) * 0.85)

                claims.append(_build_claim(
                    counter=counter,
                    member_idx=midx,
                    members=members,
                    provider_idx=pidx,
                    providers=providers,
                    service_date=svc_date,
                    place_of_service=PLACE_OFFICE,
                    cpt_code=lab_code,
                    cpt_modifier=None,
                    dx_primary=icd["icd_code"],
                    dx_2=None,
                    dx_3=None,
                    dx_4=None,
                    amount_billed=billed_lab,
                    amount_allowed=allowed_lab,
                    amount_paid=paid_lab,
                    units=1,
                    length_of_stay=None,
                    drg_code=None,
                    revenue_code=None,
                    plan_id=None,
                    referring_provider_idx=None,
                    fraud_tag="M12_lab_abuse",
                ))
    return claims


def _gen_m13_ghost(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M13 Ghost providers: 2 inactive/OIG-excluded providers still submitting. ~40 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M13_ghost")
    per_provider = 20  # 2 * 20 = 40

    for pidx in prov_idxs:
        # Recent claims (within last 3 months)
        recent_start = ref_date - timedelta(days=90)
        for _ in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            days_offset = rng.randint(0, 90)
            svc_date = recent_start + timedelta(days=days_offset)
            if svc_date > ref_date:
                svc_date = ref_date
            cpt_code = rng.choice(EM_OFFICE_CODES)
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 120.0
            billed = _d(base_price * rng.uniform(1.0, 1.20))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M13_ghost",
            ))
    return claims


def _gen_m14_double_dip(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M14 Double dipping: 1 provider bills same service to 2 plan_ids. ~25 claim pairs (50 claims)."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M14_double_dip")
    # Use dual plan IDs for the double-dip
    plan_pairs = [
        ("MA-HMO-001", "COM-PPO-020"),
        ("MA-PPO-002", "COM-HMO-010"),
        ("MA-PFFS-003", "COM-PPO-020"),
    ]

    for pidx in prov_idxs:
        for _ in range(25):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = rng.choice(EM_OFFICE_CODES + OUTPATIENT_PROCEDURE_CODES)
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 150.0
            billed = _d(base_price * rng.uniform(1.0, 1.15))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)
            plan_a, plan_b = rng.choice(plan_pairs)

            # Claim to payer A
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=plan_a,
                referring_provider_idx=None,
                fraud_tag="M14_double_dip",
            ))
            # Same claim to payer B
            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=plan_b,
                referring_provider_idx=None,
                fraud_tag="M14_double_dip",
            ))
    return claims


def _gen_m15_telehealth(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M15 Telehealth fraud: 2 providers with >40 telehealth claims per day. ~100 claims total.

    Concentrates claims on a few high-volume days so the per-day threshold triggers.
    """
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M15_telehealth")
    per_provider = 50  # 2 * 50 = 100

    for pidx in prov_idxs:
        # Pick 1 high-volume day to concentrate claims (>40 on that day)
        high_vol_date = _random_service_date(rng, ref_date)
        high_vol_count = rng.randint(42, 50)
        remaining = per_provider - high_vol_count

        for claim_num in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            if claim_num < high_vol_count:
                svc_date = high_vol_date
            else:
                svc_date = _random_service_date(rng, ref_date)
            # Bill telehealth codes at non-facility (in-person) rates
            cpt_code = rng.choice(TELEHEALTH_CODES)
            cpt_rec = cpt_lookup.get(cpt_code)
            # Use the higher non-facility price (should be facility for telehealth)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 100.0
            billed = _d(base_price * rng.uniform(1.0, 1.15))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))
            icd = _pick_icd(rng, icd_codes)

            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_TELEHEALTH,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd["icd_code"],
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M15_telehealth",
            ))
    return claims


def _gen_m16_chart_padding(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
) -> list[dict]:
    """M16 Chart padding: 2 providers with >6 diagnosis codes per claim. ~80 claims."""
    claims: list[dict] = []
    prov_idxs = _provider_indices_for_tag(providers, "M16_chart_padding")
    per_provider = 40  # 2 * 40 = 80

    all_icd_codes_list = [c["icd_code"] for c in icd_codes]

    for pidx in prov_idxs:
        for _ in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            svc_date = _random_service_date(rng, ref_date)
            cpt_code = rng.choice(EM_OFFICE_CODES)
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 150.0
            billed = _d(base_price * rng.uniform(1.10, 1.30))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))

            # Pack 7+ diagnosis codes (we store primary + 3 additional but mark tag for pattern)
            dx_sample = rng.sample(all_icd_codes_list, min(8, len(all_icd_codes_list)))

            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=dx_sample[0],
                dx_2=dx_sample[1] if len(dx_sample) > 1 else None,
                dx_3=dx_sample[2] if len(dx_sample) > 2 else None,
                dx_4=dx_sample[3] if len(dx_sample) > 3 else None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M16_chart_padding",
            ))
    return claims


# ---------------------------------------------------------------------------
# M6 — Medically Unnecessary (generated from normal providers for variety)
# ---------------------------------------------------------------------------

def _gen_m6_unnecessary(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    normal_member_idxs: list[int],
    normal_provider_idxs: list[int],
) -> list[dict]:
    """M6 Medically unnecessary: CPT-ICD mismatches (e.g., knee MRI for a cold). ~100 claims.

    Picks 4 providers from the normal pool and gives them mismatched claims.
    """
    claims: list[dict] = []
    # Pick 4 normal providers to serve as M6 offenders
    m6_providers = normal_provider_idxs[:4] if len(normal_provider_idxs) >= 4 else normal_provider_idxs
    per_provider = 25  # 4 * 25 = 100

    # Define clear mismatches: expensive imaging for unrelated simple diagnoses
    mismatches = [
        ("73721", "J00"),      # Knee MRI for common cold
        ("73721", "J06.9"),    # Knee MRI for upper respiratory infection
        ("70553", "E11.9"),    # Brain MRI for uncomplicated diabetes
        ("73221", "J00"),      # Shoulder MRI for common cold
        ("74177", "Z23"),      # CT abdomen for immunization visit
        ("77067", "M54.5"),    # Mammography for low back pain (if male)
    ]

    for pidx in m6_providers:
        for _ in range(per_provider):
            midx = rng.choice(normal_member_idxs)
            cpt_code, icd_code = rng.choice(mismatches)
            svc_date = _random_service_date(rng, ref_date)
            cpt_rec = cpt_lookup.get(cpt_code)
            base_price = float(cpt_rec["non_facility_price"]) if cpt_rec else 300.0
            billed = _d(base_price * rng.uniform(1.0, 1.20))
            allowed = _d(base_price)
            paid = _d(float(allowed) * rng.uniform(0.78, 0.85))

            claims.append(_build_claim(
                counter=counter,
                member_idx=midx,
                members=members,
                provider_idx=pidx,
                providers=providers,
                service_date=svc_date,
                place_of_service=PLACE_OFFICE,
                cpt_code=cpt_code,
                cpt_modifier=None,
                dx_primary=icd_code,
                dx_2=None,
                dx_3=None,
                dx_4=None,
                amount_billed=billed,
                amount_allowed=allowed,
                amount_paid=paid,
                units=1,
                length_of_stay=None,
                drg_code=None,
                revenue_code=None,
                plan_id=None,
                referring_provider_idx=None,
                fraud_tag="M6_unnecessary",
            ))
    return claims


# ---------------------------------------------------------------------------
# Normal (clean) claims generator
# ---------------------------------------------------------------------------

def _gen_normal_claims(
    rng: random.Random,
    counter: list[int],
    providers: list[dict],
    members: list[dict],
    cpt_lookup: dict[str, dict],
    icd_codes: list[dict],
    ref_date: date,
    target_count: int,
    normal_member_idxs: list[int],
    normal_provider_idxs: list[int],
    all_provider_idxs: list[int],
) -> list[dict]:
    """Generate ~target_count normal (non-fraudulent) claims with realistic patterns.

    Claims are distributed across providers and members with:
    - Weighted CPT distribution (E&M visits most common)
    - Realistic place-of-service mix
    - Appropriate ICD-CPT pairings from reference data
    - Normal billing jitter around CMS rates
    - Occasional referrals (~10% of claims)
    - Occasional modifiers at normal rates (~25%)
    - Occasional secondary diagnoses (~40%)
    """
    claims: list[dict] = []

    # Build weighted CPT pool: E&M heavy, some surgery, some radiology, some lab
    cpt_weights: list[tuple[str, float]] = []
    for code in cpt_lookup:
        cat = cpt_lookup[code].get("category", "")
        if cat == "E&M":
            cpt_weights.append((code, 5.0))
        elif cat == "Lab":
            cpt_weights.append((code, 2.0))
        elif cat == "Radiology":
            cpt_weights.append((code, 1.0))
        elif cat == "Surgery":
            cpt_weights.append((code, 0.5))
        elif cat == "Medicine":
            cpt_weights.append((code, 1.5))
        elif cat == "DME":
            cpt_weights.append((code, 0.2))
        else:
            cpt_weights.append((code, 0.3))

    cpt_pool = [c for c, _ in cpt_weights]
    cpt_w = [w for _, w in cpt_weights]

    # Build ICD lookup by valid CPT for medical-necessity matching
    icd_by_cpt: dict[str, list[dict]] = {}
    for icd in icd_codes:
        for valid_cpt in icd.get("valid_cpt_codes", []):
            icd_by_cpt.setdefault(valid_cpt, []).append(icd)

    for _ in range(target_count):
        # Pick provider: mostly normal, but also let tagged providers generate some clean claims
        if rng.random() < 0.85:
            pidx = rng.choice(normal_provider_idxs)
        else:
            pidx = rng.choice(all_provider_idxs)

        midx = rng.choice(normal_member_idxs)
        member = members[midx]
        svc_date = _random_service_date(rng, ref_date)

        # Weighted CPT selection
        cpt_code = rng.choices(cpt_pool, weights=cpt_w, k=1)[0]
        cpt_rec = cpt_lookup[cpt_code]
        cat = cpt_rec.get("category", "E&M")

        # Determine place of service
        if cpt_code in EM_HOSPITAL_CODES:
            pos = PLACE_INPATIENT
        elif cpt_code in EM_ER_CODES:
            pos = PLACE_ER
        elif cpt_code in TELEHEALTH_CODES:
            pos = PLACE_TELEHEALTH
        elif rng.random() < 0.03:
            pos = PLACE_TELEHEALTH
        else:
            pos = PLACE_OFFICE

        # Pick a medically appropriate ICD code
        matching_icds = icd_by_cpt.get(cpt_code, [])
        if matching_icds:
            icd = rng.choice(matching_icds)
        else:
            icd = _pick_icd(rng, icd_codes)

        # Gender appropriateness check
        gender_spec = icd.get("gender_specific")
        if gender_spec and gender_spec != member.get("_gender"):
            icd = _pick_icd(rng, icd_codes)

        # Billing: normal jitter around CMS rate
        if pos in (PLACE_INPATIENT, PLACE_ER):
            base = float(cpt_rec.get("facility_price", Decimal("100.00")))
        else:
            base = float(cpt_rec.get("non_facility_price", Decimal("100.00")))

        billed = _d(base * rng.uniform(NORMAL_JITTER_LOW, NORMAL_JITTER_HIGH))
        allowed = _d(base * rng.uniform(0.95, 1.05))
        # Paid is allowed minus copay portion
        paid = _d(float(allowed) * rng.uniform(0.72, 0.88))

        # Modifier: ~25% normal usage, mostly modifier 25
        cpt_modifier = None
        if rng.random() < 0.25:
            cpt_modifier = rng.choices(["25", "59", "76"], weights=[0.6, 0.3, 0.1], k=1)[0]

        # Secondary diagnoses: ~40% of claims have at least one
        dx_2 = dx_3 = dx_4 = None
        if rng.random() < 0.40:
            n_sec = rng.choices([1, 2, 3], weights=[0.6, 0.3, 0.1], k=1)[0]
            sec = _pick_secondary_dx(rng, icd_codes, icd["icd_code"], n_sec)
            dx_2 = sec[0]
            dx_3 = sec[1] if n_sec >= 2 else None
            dx_4 = sec[2] if n_sec >= 3 else None

        # Referral: ~10% of non-ER, non-hospital claims
        referring_pidx = None
        if pos == PLACE_OFFICE and rng.random() < 0.10:
            ref_candidates = [i for i in normal_provider_idxs if i != pidx]
            if ref_candidates:
                referring_pidx = rng.choice(ref_candidates)

        # Inpatient specifics
        los = None
        drg = None
        rev_code = None
        claim_type = "professional"
        if pos == PLACE_INPATIENT:
            los = rng.randint(2, 10)
            drg = rng.choice(["470", "473", "291", "392", "743", "871"])
            rev_code = rng.choice(["0120", "0250", "0300", "0450"])
            claim_type = "institutional"
        elif pos == PLACE_ER:
            rev_code = "0450"

        units = 1
        if cat == "Medicine" and cpt_code in ("97110", "97140"):
            units = rng.randint(1, 4)  # therapy often billed in 15-min units
            billed = _d(float(billed) * units)
            allowed = _d(float(allowed) * units)
            paid = _d(float(paid) * units)

        claims.append(_build_claim(
            counter=counter,
            member_idx=midx,
            members=members,
            provider_idx=pidx,
            providers=providers,
            service_date=svc_date,
            place_of_service=pos,
            cpt_code=cpt_code,
            cpt_modifier=cpt_modifier,
            dx_primary=icd["icd_code"],
            dx_2=dx_2,
            dx_3=dx_3,
            dx_4=dx_4,
            amount_billed=billed,
            amount_allowed=allowed,
            amount_paid=paid,
            units=units,
            length_of_stay=los,
            drg_code=drg,
            revenue_code=rev_code,
            plan_id=None,
            referring_provider_idx=referring_pidx,
            fraud_tag=None,
            claim_type=claim_type,
        ))

    return claims


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_medical_claims(
    rng: random.Random,
    providers: list[dict],
    members: list[dict],
    cpt_codes: list[dict],
    icd_codes: list[dict],
    ref_date: date,
) -> list[dict]:
    """Generate ~15,000 medical claims with fraud scenarios for rules M1-M16.

    Parameters
    ----------
    rng : random.Random
        Seeded random number generator for deterministic output.
    providers : list[dict]
        Provider dicts as returned by ``generate_providers()``.
    members : list[dict]
        Member dicts as returned by ``generate_members()``.
    cpt_codes : list[dict]
        CPT reference records from ``reference_data.CPT_CODES``.
    icd_codes : list[dict]
        ICD reference records from ``reference_data.ICD_CODES``.
    ref_date : date
        Reference date (anchor for service-date generation).

    Returns
    -------
    list[dict]
        List of claim dicts ready for database insertion.
    """
    # Build CPT lookup by code for O(1) access
    cpt_lookup: dict[str, dict] = {c["cpt_code"]: c for c in cpt_codes}

    # Pre-compute useful index lists
    normal_member_idxs = _normal_members(members)
    normal_provider_idxs = _normal_providers(providers)
    all_provider_idxs = list(range(len(providers)))

    # Sequential claim-ID counter (mutable single-element list)
    counter: list[int] = [0]

    # ── Generate fraud scenario claims ──
    all_claims: list[dict] = []

    # M1: Upcoding (~200 claims)
    all_claims.extend(_gen_m1_upcoding(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M2: Unbundling (~80 clusters -> ~280-400 individual claims)
    all_claims.extend(_gen_m2_unbundling(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M3: Duplicate billing (~100 pairs -> 200 claims)
    all_claims.extend(_gen_m3_duplicate(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M4: Phantom billing (~60 claims)
    all_claims.extend(_gen_m4_phantom(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M5: Kickback/Self-referral (~150 claims)
    all_claims.extend(_gen_m5_kickback(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M6: Medically Unnecessary (~100 claims)
    all_claims.extend(_gen_m6_unnecessary(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date,
        normal_member_idxs, normal_provider_idxs,
    ))

    # M7: Provider Collusion (~80 claims = 40 pairs)
    all_claims.extend(_gen_m7_collusion(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date,
    ))

    # M8: Modifier Misuse (~120 claims)
    all_claims.extend(_gen_m8_modifier(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M9: Copay Waiver (~180 claims)
    all_claims.extend(_gen_m9_copay_waiver(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M10: IP/OP Misclassification (~50 claims)
    all_claims.extend(_gen_m10_misclass(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M11: DME Fraud (~30 claims)
    all_claims.extend(_gen_m11_dme(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M12: Lab/Diagnostic Abuse (~200 claims)
    all_claims.extend(_gen_m12_lab_abuse(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M13: Ghost Providers (~40 claims)
    all_claims.extend(_gen_m13_ghost(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M14: Double Dipping (~50 claims = 25 pairs)
    all_claims.extend(_gen_m14_double_dip(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M15: Telehealth Fraud (~100 claims)
    all_claims.extend(_gen_m15_telehealth(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    # M16: Chart Padding (~80 claims)
    all_claims.extend(_gen_m16_chart_padding(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date, normal_member_idxs,
    ))

    fraud_count = len(all_claims)

    # ── Generate normal (clean) claims ──
    # Target ~15,000 total; remainder after fraud claims is filled with normals
    normal_target = max(15_000 - fraud_count, 12_000)

    all_claims.extend(_gen_normal_claims(
        rng, counter, providers, members, cpt_lookup, icd_codes, ref_date,
        target_count=normal_target,
        normal_member_idxs=normal_member_idxs,
        normal_provider_idxs=normal_provider_idxs,
        all_provider_idxs=all_provider_idxs,
    ))

    # Shuffle to avoid ordering artifacts in downstream analysis
    rng.shuffle(all_claims)

    return all_claims
