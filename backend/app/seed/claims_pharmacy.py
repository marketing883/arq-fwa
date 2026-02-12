"""Generate ~20,000 synthetic pharmacy claims with fraud scenarios for rules P1-P13.

Each fraud scenario is injected at specific volumes to guarantee the rule engine
has detectable patterns.  Normal (clean) claims fill the remainder to reach
the ~20,000 target.

Exported function
-----------------
generate_pharmacy_claims(rng, providers, pharmacies, members, ndc_codes, ref_date)
    -> list[dict]
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_BATCH_ID = "SEED-BATCH-001"
_CLAIM_PREFIX = "RX-2025-"

# Target volumes per fraud scenario (approximate)
_TARGET_NORMAL = 19_000
_TARGET_P1 = 30
_TARGET_P2 = 80
_TARGET_P3 = 60
_TARGET_P4 = 200
_TARGET_P5 = 150
_TARGET_P6_PHANTOM_PHARMACY = 60
_TARGET_P6_PHANTOM_MEMBER = 60
_TARGET_P7 = 100
_TARGET_P8 = 120
_TARGET_P9 = 20
_TARGET_P10 = 50
_TARGET_P11 = 25
_TARGET_P12 = 40
_TARGET_P13 = 80


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _quantize(v: float | Decimal) -> Decimal:
    """Round to two decimal places."""
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _random_date_in_range(rng, start: date, end: date) -> date:
    """Return a random date between *start* and *end* (inclusive)."""
    delta = (end - start).days
    if delta <= 0:
        return start
    return start + timedelta(days=rng.randint(0, delta))


def _build_claim(
    seq: int,
    member: dict,
    pharmacy: dict,
    prescriber: dict,
    fill_date: date,
    ndc: dict,
    quantity: int,
    days_supply: int,
    refill_number: int,
    amount_billed: Decimal,
    fraud_tag: str | None,
    prior_auth: bool = False,
) -> dict:
    """Assemble a single claim dict that matches the PharmacyClaim model."""
    amount_allowed = _quantize(amount_billed * Decimal("0.85"))
    copay = _quantize(amount_billed * Decimal("0.10"))
    amount_paid = _quantize(amount_allowed - copay)
    if amount_paid < Decimal("0"):
        amount_paid = Decimal("0.00")

    return {
        "claim_id": f"{_CLAIM_PREFIX}{seq:06d}",
        "member_id": member["_index"],
        "pharmacy_id": pharmacy["_index"],
        "prescriber_id": prescriber["_index"],
        "fill_date": fill_date,
        "ndc_code": ndc["ndc_code"],
        "drug_name": ndc["proprietary_name"],
        "drug_class": ndc.get("therapeutic_class"),
        "is_generic": not ndc.get("generic_available", False),
        "is_controlled": ndc.get("dea_schedule") is not None,
        "dea_schedule": ndc.get("dea_schedule"),
        "quantity_dispensed": Decimal(str(quantity)),
        "days_supply": days_supply,
        "refill_number": refill_number,
        "amount_billed": _quantize(amount_billed),
        "amount_allowed": amount_allowed,
        "amount_paid": amount_paid,
        "copay": copay,
        "prescriber_npi": prescriber["npi"],
        "pharmacy_npi": pharmacy["npi"],
        "prior_auth": prior_auth,
        "status": "processed",
        "batch_id": _BATCH_ID,
        "_fraud_tag": fraud_tag,
    }


# ---------------------------------------------------------------------------
# NDC helper look-ups
# ---------------------------------------------------------------------------

def _controlled_ndcs(ndc_codes: list[dict]) -> list[dict]:
    return [n for n in ndc_codes if n.get("dea_schedule") in ("CII", "CIII")]


def _schedule_ii_ndcs(ndc_codes: list[dict]) -> list[dict]:
    return [n for n in ndc_codes if n.get("dea_schedule") == "CII"]


def _non_controlled_ndcs(ndc_codes: list[dict]) -> list[dict]:
    return [n for n in ndc_codes if n.get("dea_schedule") is None]


def _brand_with_generic(ndc_codes: list[dict]) -> list[dict]:
    """Return NDCs that are brand-name AND have a generic alternative available."""
    return [
        n for n in ndc_codes
        if n.get("generic_available") and n.get("generic_ndc") and n["generic_ndc"] != n["ndc_code"]
    ]


def _compound_ndcs(ndc_codes: list[dict]) -> list[dict]:
    return [n for n in ndc_codes if n.get("therapeutic_class") == "Compound"]


def _all_ndcs(ndc_codes: list[dict]) -> list[dict]:
    return list(ndc_codes)


# ---------------------------------------------------------------------------
# Provider / pharmacy / member selectors
# ---------------------------------------------------------------------------

def _providers_by_tag(providers: list[dict], tag: str) -> list[dict]:
    return [p for p in providers if p.get("_fraud_tag") == tag]


def _pharmacies_by_tag(pharmacies: list[dict], tag: str) -> list[dict]:
    return [p for p in pharmacies if p.get("_fraud_tag") == tag]


def _members_by_tag(members: list[dict], tag: str) -> list[dict]:
    return [m for m in members if m.get("_fraud_tag") == tag]


def _normal_providers(providers: list[dict]) -> list[dict]:
    return [p for p in providers if p.get("_fraud_tag") is None and p.get("is_active", True)]


def _normal_pharmacies(pharmacies: list[dict]) -> list[dict]:
    return [p for p in pharmacies if p.get("_fraud_tag") is None]


def _normal_members(members: list[dict]) -> list[dict]:
    return [m for m in members if m.get("_fraud_tag") is None]


# ---------------------------------------------------------------------------
# Fraud scenario generators
# ---------------------------------------------------------------------------

def _gen_p1_prescription_forgery(
    rng, seq: int, members: list[dict], pharmacies: list[dict],
    ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P1: Claims with non-existent prescriber NPIs (NPI starting with '9')."""
    claims: list[dict] = []
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    controlled = _controlled_ndcs(ndc_codes) or ndc_codes[:5]
    # Pick a pool of normal members for forgery claims
    pool = _normal_members(members)
    if len(pool) < 30:
        pool = members[:100]

    for i in range(_TARGET_P1):
        member = rng.choice(pool)
        pharmacy = rng.choice(normal_pharms)
        ndc = rng.choice(controlled)
        fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
        qty = rng.choice([30, 60, 90])
        days = qty
        billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.3))

        # Fake prescriber stub -- NPI starts with "9" and does not match any real provider
        fake_npi = f"9{rng.randint(100000000, 999999999)}"
        fake_prescriber = {
            "_index": -1,  # sentinel: does not exist in providers table
            "npi": fake_npi,
        }

        claim = _build_claim(
            seq=seq, member=member, pharmacy=pharmacy, prescriber=fake_prescriber,
            fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=days,
            refill_number=0, amount_billed=billed, fraud_tag="P1_prescription_forgery",
        )
        # Override prescriber_npi explicitly (it is the fake NPI)
        claim["prescriber_npi"] = fake_npi
        claims.append(claim)
        seq += 1

    return claims, seq


def _gen_p2_doctor_shopping(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P2: 10 members visit 5+ unique prescribers for controlled substances in 90 days."""
    claims: list[dict] = []
    flagged = _members_by_tag(members, "P2_doctor_shopping")
    normal_provs = _normal_providers(providers)
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    controlled = _schedule_ii_ndcs(ndc_codes) or _controlled_ndcs(ndc_codes) or ndc_codes[:4]

    per_member = max(1, _TARGET_P2 // max(len(flagged), 1))

    for member in flagged:
        # Each member uses 5-7 unique prescribers within a 90-day window
        prescriber_pool = rng.sample(normal_provs, min(7, len(normal_provs)))
        window_start = ref_date - timedelta(days=rng.randint(91, 180))
        window_end = window_start + timedelta(days=90)
        if window_end > ref_date:
            window_end = ref_date

        for j in range(per_member):
            prescriber = prescriber_pool[j % len(prescriber_pool)]
            pharmacy = rng.choice(normal_pharms)
            ndc = rng.choice(controlled)
            fill_date = _random_date_in_range(rng, window_start, window_end)
            qty = rng.choice([30, 60])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=0, amount_billed=billed, fraud_tag="P2_doctor_shopping",
            ))
            seq += 1

    return claims, seq


def _gen_p3_pharmacy_shopping(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P3: 8 members fill the same drug at 4+ pharmacies within 60 days."""
    claims: list[dict] = []
    flagged = _members_by_tag(members, "P3_pharmacy_shopping")
    normal_provs = _normal_providers(providers)
    all_pharms = _normal_pharmacies(pharmacies) or pharmacies
    controlled = _controlled_ndcs(ndc_codes) or ndc_codes[:5]

    per_member = max(1, _TARGET_P3 // max(len(flagged), 1))

    for member in flagged:
        # Pick one drug that this member will shop around
        drug_ndc = rng.choice(controlled)
        prescriber = rng.choice(normal_provs)
        pharm_pool = rng.sample(all_pharms, min(6, len(all_pharms)))
        window_start = ref_date - timedelta(days=rng.randint(61, 150))
        window_end = window_start + timedelta(days=60)
        if window_end > ref_date:
            window_end = ref_date

        for j in range(per_member):
            pharmacy = pharm_pool[j % len(pharm_pool)]
            fill_date = _random_date_in_range(rng, window_start, window_end)
            qty = rng.choice([30, 60])
            billed = _quantize(float(drug_ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=drug_ndc, quantity=qty, days_supply=30,
                refill_number=j, amount_billed=billed, fraud_tag="P3_pharmacy_shopping",
            ))
            seq += 1

    return claims, seq


def _gen_p4_early_refill(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P4: ~200 claims where refill happens at <75% of days_supply."""
    claims: list[dict] = []
    flagged = _members_by_tag(members, "P4_early_refill")
    normal_provs = _normal_providers(providers)
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    controlled = _controlled_ndcs(ndc_codes) or ndc_codes[:5]
    non_controlled = _non_controlled_ndcs(ndc_codes) or ndc_codes

    per_member = max(1, _TARGET_P4 // max(len(flagged), 1))

    for member in flagged:
        prescriber = rng.choice(normal_provs)
        pharmacy = rng.choice(normal_pharms)
        # Mix of controlled and non-controlled for realism
        drug_ndc = rng.choice(controlled + non_controlled[:3])
        # Primarily use 30-day supply so refill chains produce enough claims
        days_supply = rng.choice([30, 30, 30, 60])

        # Generate a chain of early refills starting far enough back
        # to produce ~20 claims per member (10 members x 20 = 200)
        current_date = ref_date - timedelta(days=365)
        for j in range(per_member):
            if current_date > ref_date:
                break
            billed = _quantize(float(drug_ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))
            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=current_date, ndc=drug_ndc, quantity=days_supply,
                days_supply=days_supply, refill_number=j,
                amount_billed=billed, fraud_tag="P4_early_refill",
            ))
            seq += 1
            # Next refill at 40-70% of days_supply  (< 75% threshold)
            early_days = int(days_supply * rng.uniform(0.40, 0.70))
            current_date = current_date + timedelta(days=max(early_days, 5))

    return claims, seq


def _gen_p5_controlled_diversion(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P5: 3 prescribers where >80% of their Rx are Schedule II-III. ~150 claims."""
    claims: list[dict] = []
    diversion_provs = _providers_by_tag(providers, "P5_diversion")
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    normal_mems = _normal_members(members)
    controlled = _controlled_ndcs(ndc_codes) or ndc_codes[:5]
    non_controlled = _non_controlled_ndcs(ndc_codes) or ndc_codes

    per_prescriber = max(1, _TARGET_P5 // max(len(diversion_provs), 1))

    for prescriber in diversion_provs:
        for j in range(per_prescriber):
            member = rng.choice(normal_mems)
            pharmacy = rng.choice(normal_pharms)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
            # >80% controlled
            if rng.random() < 0.85:
                ndc = rng.choice(controlled)
            else:
                ndc = rng.choice(non_controlled)
            qty = rng.choice([30, 60, 90, 120])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.3))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=rng.randint(0, 3), amount_billed=billed,
                fraud_tag="P5_diversion",
            ))
            seq += 1

    return claims, seq


def _gen_p6_phantom_pharmacy(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P6 (pharmacy side): 1 phantom pharmacy bills for members with no medical history."""
    claims: list[dict] = []
    phantom_pharms = _pharmacies_by_tag(pharmacies, "P6_phantom")
    # Members tagged as 'rx only' -- they have Rx but no medical claims
    phantom_members = _members_by_tag(members, "P6_phantom_rx_only")
    normal_provs = _normal_providers(providers)
    all_ndcs = _all_ndcs(ndc_codes)

    if not phantom_pharms:
        return claims, seq

    pharmacy = phantom_pharms[0]
    per_member = max(1, _TARGET_P6_PHANTOM_PHARMACY // max(len(phantom_members), 1))

    for member in phantom_members:
        prescriber = rng.choice(normal_provs)
        for j in range(per_member):
            ndc = rng.choice(all_ndcs)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
            qty = rng.choice([30, 60, 90])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.3))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=0, amount_billed=billed,
                fraud_tag="P6_phantom",
            ))
            seq += 1

    return claims, seq


def _gen_p6_phantom_member(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """Additional P6 claims for P6_phantom_rx_only members from *normal* pharmacies.

    These are members who only have Rx claims and zero medical claims,
    spread across multiple pharmacies so the phantom-member pattern is
    detectable even outside the single phantom pharmacy.
    """
    claims: list[dict] = []
    phantom_members = _members_by_tag(members, "P6_phantom_rx_only")
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    normal_provs = _normal_providers(providers)
    all_ndcs = _all_ndcs(ndc_codes)

    per_member = max(1, _TARGET_P6_PHANTOM_MEMBER // max(len(phantom_members), 1))

    for member in phantom_members:
        prescriber = rng.choice(normal_provs)
        for j in range(per_member):
            ndc = rng.choice(all_ndcs)
            pharmacy = rng.choice(normal_pharms)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
            qty = rng.choice([30, 60, 90])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.3))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=0, amount_billed=billed,
                fraud_tag="P6_phantom_rx_only",
            ))
            seq += 1

    return claims, seq


def _gen_p7_substitution(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P7: 2 pharmacies always dispense brand when a cheaper generic exists. ~100 claims."""
    claims: list[dict] = []
    sub_pharms = _pharmacies_by_tag(pharmacies, "P7_substitution")
    brand_ndcs = _brand_with_generic(ndc_codes)
    normal_provs = _normal_providers(providers)
    normal_mems = _normal_members(members)

    if not brand_ndcs or not sub_pharms:
        return claims, seq

    per_pharmacy = max(1, _TARGET_P7 // max(len(sub_pharms), 1))

    for pharmacy in sub_pharms:
        for j in range(per_pharmacy):
            member = rng.choice(normal_mems)
            prescriber = rng.choice(normal_provs)
            ndc = rng.choice(brand_ndcs)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
            qty = rng.choice([30, 60, 90])
            # Bill at the higher brand price
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(1.0, 1.3))

            claim = _build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=rng.randint(0, 5), amount_billed=billed,
                fraud_tag="P7_substitution",
            )
            # Ensure it is marked as brand (not generic)
            claim["is_generic"] = False
            claims.append(claim)
            seq += 1

    return claims, seq


def _gen_p8_kickback(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P8: 3 prescribers send >80% of Rx to specific pharmacies. ~120 claims."""
    claims: list[dict] = []
    kick_provs = _providers_by_tag(providers, "P8_kickback")
    kick_pharms = _pharmacies_by_tag(pharmacies, "P8_kickback_rx")
    normal_mems = _normal_members(members)
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    all_ndcs = _all_ndcs(ndc_codes)

    if not kick_provs or not kick_pharms:
        return claims, seq

    per_prescriber = max(1, _TARGET_P8 // max(len(kick_provs), 1))

    for idx, prescriber in enumerate(kick_provs):
        # Map each prescriber to a preferred pharmacy
        preferred_pharm = kick_pharms[idx % len(kick_pharms)]

        for j in range(per_prescriber):
            member = rng.choice(normal_mems)
            ndc = rng.choice(all_ndcs)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
            qty = rng.choice([30, 60, 90])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))

            # >85% go to preferred pharmacy
            if rng.random() < 0.88:
                pharmacy = preferred_pharm
            else:
                pharmacy = rng.choice(normal_pharms)

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=rng.randint(0, 3), amount_billed=billed,
                fraud_tag="P8_kickback",
            ))
            seq += 1

    return claims, seq


def _gen_p9_invalid_prescriber(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P9: Prescribers with no DEA prescribe Schedule II. ~20 claims."""
    claims: list[dict] = []
    invalid_provs = _providers_by_tag(providers, "P9_invalid_prescriber")
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    normal_mems = _normal_members(members)
    sch2 = _schedule_ii_ndcs(ndc_codes)

    if not invalid_provs or not sch2:
        return claims, seq

    per_prescriber = max(1, _TARGET_P9 // max(len(invalid_provs), 1))

    for prescriber in invalid_provs:
        for j in range(per_prescriber):
            member = rng.choice(normal_mems)
            pharmacy = rng.choice(normal_pharms)
            ndc = rng.choice(sch2)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=180), ref_date)
            qty = rng.choice([30, 60])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=0, amount_billed=billed,
                fraud_tag="P9_invalid_prescriber",
            ))
            seq += 1

    return claims, seq


def _gen_p10_stockpiling(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P10: 10 members accumulate >2x calendar days of supply in 90-day windows. ~50 claims."""
    claims: list[dict] = []
    flagged = _members_by_tag(members, "P10_stockpiling")
    normal_provs = _normal_providers(providers)
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    controlled = _controlled_ndcs(ndc_codes) or ndc_codes[:5]

    per_member = max(1, _TARGET_P10 // max(len(flagged), 1))

    for member in flagged:
        prescriber = rng.choice(normal_provs)
        pharmacy = rng.choice(normal_pharms)
        drug_ndc = rng.choice(controlled)
        days_supply = 30

        # Pack many 30-day-supply fills into a 90-day window
        window_start = ref_date - timedelta(days=rng.randint(91, 200))
        current_date = window_start

        for j in range(per_member):
            if current_date > window_start + timedelta(days=90):
                break
            if current_date > ref_date:
                break
            billed = _quantize(float(drug_ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))
            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=current_date, ndc=drug_ndc, quantity=days_supply,
                days_supply=days_supply, refill_number=j,
                amount_billed=billed, fraud_tag="P10_stockpiling",
            ))
            seq += 1
            # Fills every 10-18 days for a 30-day supply => accumulates excess
            current_date = current_date + timedelta(days=rng.randint(10, 18))

    return claims, seq


def _gen_p11_compound_fraud(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P11: 1 compounding pharmacy with claims >$3000. ~25 claims."""
    claims: list[dict] = []
    compound_pharms = _pharmacies_by_tag(pharmacies, "P11_compound")
    normal_provs = _normal_providers(providers)
    normal_mems = _normal_members(members)
    compound_drugs = _compound_ndcs(ndc_codes)

    if not compound_pharms or not compound_drugs:
        return claims, seq

    pharmacy = compound_pharms[0]

    for j in range(_TARGET_P11):
        member = rng.choice(normal_mems)
        prescriber = rng.choice(normal_provs)
        ndc = rng.choice(compound_drugs)
        fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
        qty = rng.randint(1, 3)
        # High-cost compound: $3,000 - $12,000
        billed = _quantize(rng.uniform(3000.0, 12000.0))

        claims.append(_build_claim(
            seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
            fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
            refill_number=0, amount_billed=billed, fraud_tag="P11_compound",
            prior_auth=rng.random() < 0.20,  # rarely has prior auth
        ))
        seq += 1

    return claims, seq


def _gen_p12_phantom_members(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P12: Claims for members whose eligibility has ended. ~40 claims."""
    claims: list[dict] = []
    expired_members = _members_by_tag(members, "P12_phantom_member")
    normal_provs = _normal_providers(providers)
    normal_pharms = _normal_pharmacies(pharmacies) or pharmacies
    all_ndcs = _all_ndcs(ndc_codes)

    if not expired_members:
        return claims, seq

    per_member = max(1, _TARGET_P12 // max(len(expired_members), 1))
    # We need at least ~3 claims per member to hit 40
    if per_member < 3:
        per_member = 3

    count = 0
    for member in expired_members:
        elig_end = member.get("eligibility_end")
        if elig_end is None:
            continue
        prescriber = rng.choice(normal_provs)
        pharmacy = rng.choice(normal_pharms)

        for j in range(per_member):
            if count >= _TARGET_P12:
                break
            ndc = rng.choice(all_ndcs)
            # Fill date AFTER eligibility end
            days_after = rng.randint(1, 120)
            fill_date = elig_end + timedelta(days=days_after)
            if fill_date > ref_date:
                fill_date = ref_date
            qty = rng.choice([30, 60, 90])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=0, amount_billed=billed,
                fraud_tag="P12_phantom_member",
            ))
            seq += 1
            count += 1

        if count >= _TARGET_P12:
            break

    return claims, seq


def _gen_p13_collusion(
    rng, seq: int, providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """P13: 2 pharmacies + specific prescribers with abnormally high volume. ~80 claims."""
    claims: list[dict] = []
    collusion_pharms = _pharmacies_by_tag(pharmacies, "P13_collusion")
    # Use the first few normal providers as the colluding prescribers
    normal_provs = _normal_providers(providers)
    normal_mems = _normal_members(members)
    all_ndcs = _all_ndcs(ndc_codes)

    if not collusion_pharms or len(normal_provs) < 2:
        return claims, seq

    # Pick 2 dedicated prescribers to collude with the 2 pharmacies
    colluding_prescribers = normal_provs[:2]
    per_pair = max(1, _TARGET_P13 // max(len(collusion_pharms), 1))

    for idx, pharmacy in enumerate(collusion_pharms):
        prescriber = colluding_prescribers[idx % len(colluding_prescribers)]

        for j in range(per_pair):
            member = rng.choice(normal_mems)
            ndc = rng.choice(all_ndcs)
            fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
            qty = rng.choice([30, 60, 90])
            billed = _quantize(float(ndc["avg_wholesale_price"]) * rng.uniform(0.9, 1.2))

            claims.append(_build_claim(
                seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
                fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=30,
                refill_number=rng.randint(0, 5), amount_billed=billed,
                fraud_tag="P13_collusion",
            ))
            seq += 1

    return claims, seq


# ---------------------------------------------------------------------------
# Normal (clean) claims generator
# ---------------------------------------------------------------------------

def _gen_normal_claims(
    rng, seq: int, count: int,
    providers: list[dict], pharmacies: list[dict],
    members: list[dict], ndc_codes: list[dict], ref_date: date,
) -> tuple[list[dict], int]:
    """Generate *count* clean pharmacy claims distributed across 12 months."""
    claims: list[dict] = []
    norm_provs = _normal_providers(providers)
    norm_pharms = _normal_pharmacies(pharmacies) or pharmacies
    norm_mems = _normal_members(members)
    controlled = _controlled_ndcs(ndc_codes)
    non_controlled = _non_controlled_ndcs(ndc_codes)
    brand_ndcs = _brand_with_generic(ndc_codes)
    all_ndcs = _all_ndcs(ndc_codes)

    if not norm_provs:
        norm_provs = providers[:100]
    if not norm_mems:
        norm_mems = members[:500]

    for _ in range(count):
        member = rng.choice(norm_mems)
        prescriber = rng.choice(norm_provs)
        pharmacy = rng.choice(norm_pharms)

        # Drug selection weighted toward non-controlled (realistic mix)
        roll = rng.random()
        if roll < 0.15 and controlled:
            ndc = rng.choice(controlled)
        elif roll < 0.20 and brand_ndcs:
            # Some brand dispensing is normal
            ndc = rng.choice(brand_ndcs)
        else:
            if non_controlled:
                ndc = rng.choice(non_controlled)
            else:
                ndc = rng.choice(all_ndcs)

        fill_date = _random_date_in_range(rng, ref_date - timedelta(days=365), ref_date)
        days_supply = rng.choice([7, 14, 30, 30, 30, 60, 90])
        qty = days_supply * rng.choice([1, 2])
        refill_number = rng.choices([0, 1, 2, 3, 4, 5], weights=[40, 25, 15, 10, 7, 3])[0]

        base_price = float(ndc["avg_wholesale_price"])
        # For normal claims, if a generic exists, use the generic most of the time
        if ndc.get("generic_available") and ndc.get("generic_price") and rng.random() < 0.85:
            base_price = float(ndc["generic_price"])
            effective_ndc = dict(ndc)
            if ndc.get("generic_ndc") and ndc["generic_ndc"] != ndc["ndc_code"]:
                # Switch to the generic NDC
                generic_match = [n for n in ndc_codes if n["ndc_code"] == ndc["generic_ndc"]]
                if generic_match:
                    effective_ndc = generic_match[0]
                    ndc = effective_ndc

        billed = _quantize(base_price * rng.uniform(0.85, 1.15))
        if billed < Decimal("1.00"):
            billed = Decimal("5.00")

        claims.append(_build_claim(
            seq=seq, member=member, pharmacy=pharmacy, prescriber=prescriber,
            fill_date=fill_date, ndc=ndc, quantity=qty, days_supply=days_supply,
            refill_number=refill_number, amount_billed=billed,
            fraud_tag=None,
            prior_auth=rng.random() < 0.05,
        ))
        seq += 1

    return claims, seq


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate_pharmacy_claims(
    rng,
    providers: list[dict],
    pharmacies: list[dict],
    members: list[dict],
    ndc_codes: list[dict],
    ref_date: date,
) -> list[dict]:
    """Generate approximately 20,000 pharmacy claims with fraud scenarios P1-P13.

    Parameters
    ----------
    rng : random.Random
        Seeded random instance for deterministic output.
    providers : list[dict]
        Output of ``generate_providers()``.
    pharmacies : list[dict]
        Output of ``generate_pharmacies()``.
    members : list[dict]
        Output of ``generate_members()``.
    ndc_codes : list[dict]
        NDC reference list (``reference_data.NDC_CODES``).
    ref_date : date
        Anchor date; claims span the preceding 12 months.

    Returns
    -------
    list[dict]
        Claim dicts ready for database insertion. Each dict has all fields
        matching the ``PharmacyClaim`` model plus ``_fraud_tag`` metadata.
    """
    seq = 1  # sequential claim number
    all_claims: list[dict] = []

    # ── Fraud scenario claims ──────────────────────────────────────────
    p1, seq = _gen_p1_prescription_forgery(rng, seq, members, pharmacies, ndc_codes, ref_date)
    all_claims.extend(p1)

    p2, seq = _gen_p2_doctor_shopping(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p2)

    p3, seq = _gen_p3_pharmacy_shopping(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p3)

    p4, seq = _gen_p4_early_refill(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p4)

    p5, seq = _gen_p5_controlled_diversion(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p5)

    p6a, seq = _gen_p6_phantom_pharmacy(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p6a)

    p6b, seq = _gen_p6_phantom_member(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p6b)

    p7, seq = _gen_p7_substitution(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p7)

    p8, seq = _gen_p8_kickback(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p8)

    p9, seq = _gen_p9_invalid_prescriber(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p9)

    p10, seq = _gen_p10_stockpiling(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p10)

    p11, seq = _gen_p11_compound_fraud(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p11)

    p12, seq = _gen_p12_phantom_members(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p12)

    p13, seq = _gen_p13_collusion(rng, seq, providers, pharmacies, members, ndc_codes, ref_date)
    all_claims.extend(p13)

    # ── Normal claims ──────────────────────────────────────────────────
    fraud_count = len(all_claims)
    normal_target = max(0, _TARGET_NORMAL - fraud_count)
    # Ensure the total is around 20,000
    normal_target = max(normal_target, 20_000 - fraud_count)

    normal, seq = _gen_normal_claims(
        rng, seq, normal_target,
        providers, pharmacies, members, ndc_codes, ref_date,
    )
    all_claims.extend(normal)

    # ── Shuffle to avoid ordering artefacts ────────────────────────────
    rng.shuffle(all_claims)

    # ── Re-sequence claim IDs after shuffle ────────────────────────────
    for i, claim in enumerate(all_claims, start=1):
        claim["claim_id"] = f"{_CLAIM_PREFIX}{i:06d}"

    return all_claims
