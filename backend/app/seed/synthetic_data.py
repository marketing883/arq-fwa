"""
Master seed orchestrator — generates and inserts all synthetic data.

Usage:
    python -m app.seed.synthetic_data          # Seed everything
    python -m app.seed.synthetic_data --clean   # Drop all data + re-seed
    python -m app.seed.synthetic_data --verify  # Just verify existing data
"""

import asyncio
import random
import sys
import time
from datetime import date
from decimal import Decimal

from sqlalchemy import text, select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.database import Base
from app.models import (
    Provider, Pharmacy, Member, MedicalClaim, PharmacyClaim,
    Rule, NDCReference, CPTReference, ICDReference,
)
from app.seed.reference_data import CPT_CODES, ICD_CODES, NDC_CODES
from app.seed.providers import generate_providers, generate_pharmacies
from app.seed.members import generate_members
from app.seed.claims_medical import generate_medical_claims
from app.seed.claims_pharmacy import generate_pharmacy_claims
from app.seed.fraud_scenarios import RULES_SEED


REF_DATE = date(2025, 10, 31)
SEED = 42


async def seed_reference_data(session: AsyncSession) -> None:
    """Seed NDC, CPT, ICD-10 reference tables."""
    print("  Seeding CPT codes...", end=" ", flush=True)
    for code in CPT_CODES:
        obj = CPTReference(**{k: v for k, v in code.items() if not k.startswith("_")})
        session.add(obj)
    await session.flush()
    print(f"{len(CPT_CODES)} codes")

    print("  Seeding ICD-10 codes...", end=" ", flush=True)
    for code in ICD_CODES:
        clean = {}
        for k, v in code.items():
            if k.startswith("_"):
                continue
            if k == "valid_cpt_codes" and isinstance(v, list):
                clean[k] = {"codes": v}
            else:
                clean[k] = v
        obj = ICDReference(**clean)
        session.add(obj)
    await session.flush()
    print(f"{len(ICD_CODES)} codes")

    print("  Seeding NDC codes...", end=" ", flush=True)
    for code in NDC_CODES:
        obj = NDCReference(**{k: v for k, v in code.items() if not k.startswith("_")})
        session.add(obj)
    await session.flush()
    print(f"{len(NDC_CODES)} codes")


async def seed_rules(session: AsyncSession) -> None:
    """Seed all 29 FWA detection rules."""
    print("  Seeding rules...", end=" ", flush=True)
    for rule_data in RULES_SEED:
        obj = Rule(
            rule_id=rule_data["rule_id"],
            category=rule_data["category"],
            fraud_type=rule_data["fraud_type"],
            claim_type=rule_data["claim_type"],
            description=rule_data["description"],
            detection_logic=rule_data["detection_logic"],
            enabled=True,
            weight=Decimal(str(rule_data["weight"])),
            thresholds=rule_data["thresholds"],
            benchmark_source=rule_data.get("benchmark_source"),
            implementation_priority=rule_data["implementation_priority"],
            version=1,
        )
        session.add(obj)
    await session.flush()
    print(f"{len(RULES_SEED)} rules")


async def seed_providers(session: AsyncSession, rng: random.Random) -> tuple[list[dict], list[dict]]:
    """Seed providers and pharmacies, return the generated data for claim generation."""
    providers_data = generate_providers(rng)
    pharmacies_data = generate_pharmacies(rng)

    print("  Seeding providers...", end=" ", flush=True)
    provider_id_map = {}
    for p in providers_data:
        clean = {k: v for k, v in p.items() if not k.startswith("_")}
        obj = Provider(**clean)
        session.add(obj)
        await session.flush()
        provider_id_map[p["_index"]] = obj.id
        p["_db_id"] = obj.id
    print(f"{len(providers_data)} providers")

    print("  Seeding pharmacies...", end=" ", flush=True)
    for ph in pharmacies_data:
        clean = {k: v for k, v in ph.items() if not k.startswith("_")}
        obj = Pharmacy(**clean)
        session.add(obj)
        await session.flush()
        ph["_db_id"] = obj.id
    print(f"{len(pharmacies_data)} pharmacies")

    return providers_data, pharmacies_data


async def seed_members(session: AsyncSession, rng: random.Random) -> list[dict]:
    """Seed members, return generated data."""
    members_data = generate_members(rng, REF_DATE)

    print("  Seeding members...", end=" ", flush=True)
    for m in members_data:
        clean = {k: v for k, v in m.items() if not k.startswith("_")}
        obj = Member(**clean)
        session.add(obj)
        await session.flush()
        m["_db_id"] = obj.id
    print(f"{len(members_data)} members")

    return members_data


def _build_id_maps(providers, pharmacies, members):
    """Build fast index→db_id lookup dicts."""
    prov_map = {p["_index"]: p["_db_id"] for p in providers}
    pharm_map = {p["_index"]: p["_db_id"] for p in pharmacies}
    mem_map = {m["_index"]: m["_db_id"] for m in members}
    return prov_map, pharm_map, mem_map


async def seed_medical_claims(
    session: AsyncSession, rng: random.Random,
    providers: list[dict], members: list[dict],
) -> int:
    """Generate and seed medical claims."""
    print("  Generating medical claims...", end=" ", flush=True)
    claims = generate_medical_claims(rng, providers, members, CPT_CODES, ICD_CODES, REF_DATE)
    print(f"{len(claims)} generated")

    prov_map = {p["_index"]: p["_db_id"] for p in providers}
    mem_map = {m["_index"]: m["_db_id"] for m in members}

    print("  Inserting medical claims...", end=" ", flush=True)
    count = 0
    batch = []
    for c in claims:
        clean = {}
        for k, v in c.items():
            if k.startswith("_"):
                continue
            if k == "member_id":
                clean[k] = mem_map.get(v, v)
            elif k == "provider_id":
                clean[k] = prov_map.get(v, v)
            elif k == "referring_provider_id" and v is not None:
                clean[k] = prov_map.get(v, v)
            else:
                clean[k] = v
        batch.append(MedicalClaim(**clean))
        count += 1

        if len(batch) >= 500:
            session.add_all(batch)
            await session.flush()
            batch = []

    if batch:
        session.add_all(batch)
        await session.flush()

    print(f"{count} inserted")
    return count


async def seed_pharmacy_claims(
    session: AsyncSession, rng: random.Random,
    providers: list[dict], pharmacies: list[dict], members: list[dict],
) -> int:
    """Generate and seed pharmacy claims."""
    print("  Generating pharmacy claims...", end=" ", flush=True)
    claims = generate_pharmacy_claims(rng, providers, pharmacies, members, NDC_CODES, REF_DATE)
    print(f"{len(claims)} generated")

    prov_map = {p["_index"]: p["_db_id"] for p in providers}
    pharm_map = {p["_index"]: p["_db_id"] for p in pharmacies}
    mem_map = {m["_index"]: m["_db_id"] for m in members}
    fallback_prov_id = providers[0]["_db_id"]

    print("  Inserting pharmacy claims...", end=" ", flush=True)
    count = 0
    batch = []
    for c in claims:
        clean = {}
        for k, v in c.items():
            if k.startswith("_"):
                continue
            if k == "member_id":
                clean[k] = mem_map.get(v, v)
            elif k == "pharmacy_id":
                clean[k] = pharm_map.get(v, v)
            elif k == "prescriber_id":
                if v == -1:
                    clean[k] = fallback_prov_id
                else:
                    clean[k] = prov_map.get(v, v)
            else:
                clean[k] = v
        batch.append(PharmacyClaim(**clean))
        count += 1

        if len(batch) >= 500:
            session.add_all(batch)
            await session.flush()
            batch = []

    if batch:
        session.add_all(batch)
        await session.flush()

    print(f"{count} inserted")
    return count


async def verify_data(session: AsyncSession) -> bool:
    """Verify all seeded data counts."""
    print("\n── Verification ──")
    checks = [
        ("providers", Provider),
        ("pharmacies", Pharmacy),
        ("members", Member),
        ("medical_claims", MedicalClaim),
        ("pharmacy_claims", PharmacyClaim),
        ("rules", Rule),
        ("cpt_reference", CPTReference),
        ("icd_reference", ICDReference),
        ("ndc_reference", NDCReference),
    ]

    all_ok = True
    for name, model in checks:
        result = await session.execute(select(func.count()).select_from(model))
        count = result.scalar()
        expected_min = {
            "providers": 200, "pharmacies": 50, "members": 2000,
            "medical_claims": 10000, "pharmacy_claims": 10000,
            "rules": 29, "cpt_reference": 40, "icd_reference": 25, "ndc_reference": 20,
        }.get(name, 1)

        status = "OK" if count >= expected_min else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  {name}: {count:,} {'':>6} [{status}] (expected >= {expected_min:,})")

    return all_ok


async def clean_all(session: AsyncSession) -> None:
    """Drop all data from all tables (preserves schema)."""
    print("Cleaning all data...")
    tables = [
        "rule_results", "risk_scores", "case_evidence", "case_notes",
        "investigation_cases", "pharmacy_claims", "medical_claims",
        "members", "pharmacies", "providers", "rules",
        "ndc_reference", "cpt_reference", "icd_reference", "audit_log",
    ]
    for table in tables:
        await session.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    await session.commit()
    print("All data cleaned.")


async def run_seed():
    """Main seed entry point."""
    start = time.time()
    engine = create_async_engine(settings.database_url, echo=False)
    async_sess = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    clean = "--clean" in sys.argv
    verify_only = "--verify" in sys.argv

    async with async_sess() as session:
        if verify_only:
            ok = await verify_data(session)
            await engine.dispose()
            sys.exit(0 if ok else 1)

        if clean:
            await clean_all(session)

        # Check if already seeded
        result = await session.execute(select(func.count()).select_from(Provider))
        if result.scalar() > 0 and not clean:
            print("Database already seeded. Use --clean to re-seed.")
            ok = await verify_data(session)
            await engine.dispose()
            sys.exit(0 if ok else 1)

        rng = random.Random(SEED)

        print("=" * 60)
        print("ArqAI FWA — Synthetic Data Seed")
        print("=" * 60)

        print("\n[1/6] Reference data")
        await seed_reference_data(session)

        print("\n[2/6] Rules")
        await seed_rules(session)

        print("\n[3/6] Providers & Pharmacies")
        providers, pharmacies = await seed_providers(session, rng)

        print("\n[4/6] Members")
        members = await seed_members(session, rng)

        print("\n[5/6] Medical Claims")
        med_count = await seed_medical_claims(session, rng, providers, members)

        print("\n[6/6] Pharmacy Claims")
        rx_count = await seed_pharmacy_claims(session, rng, providers, pharmacies, members)

        await session.commit()

        ok = await verify_data(session)

    await engine.dispose()

    elapsed = time.time() - start
    print(f"\nSeed completed in {elapsed:.1f}s")
    print(f"Total claims: {med_count + rx_count:,}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(run_seed())
