#!/bin/bash
set -e

echo "======================================"
echo "  ArqAI FWA Detection — Starting Up"
echo "======================================"

# 1. Run database migrations
echo "[1/5] Running database migrations..."
alembic upgrade head
echo "  ✓ Migrations complete"

# 2. Seed data if DB is empty
echo "[2/5] Checking seed data..."
python -c "
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.claim import MedicalClaim

async def check():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        count = (await session.execute(select(func.count()).select_from(MedicalClaim))).scalar()
    await engine.dispose()
    return count

count = asyncio.run(check())
if count == 0:
    print('  DB is empty — seeding...')
    exit(0)
else:
    print(f'  DB already has {count} medical claims — skipping seed')
    exit(1)
" && {
    echo "  Seeding all data (reference, rules, providers, members, claims)..."
    python -m app.seed.synthetic_data
    echo "  ✓ Seed data loaded"
} || echo "  ✓ Seed data already exists"

# 2b. Verify seed worked — if not, abort early
python -c "
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.claim import MedicalClaim

async def check():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        count = (await session.execute(select(func.count()).select_from(MedicalClaim))).scalar()
    await engine.dispose()
    return count

count = asyncio.run(check())
if count == 0:
    print('  ⚠ WARNING: Database has 0 claims after seeding!')
    exit(1)
else:
    print(f'  ✓ Database has {count} claims')
    exit(0)
"

# 2c. Backfill workspace_id for any records that have NULL workspace_id
# This handles seed data created after the workspace migration ran.
echo "[3/5] Backfilling workspace_id on orphaned records..."
python -c "
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings

TABLES = [
    'providers', 'pharmacies', 'members',
    'medical_claims', 'pharmacy_claims',
    'risk_scores', 'rule_results', 'investigation_cases',
]

async def backfill():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        # Get the ws-default workspace PK
        row = (await session.execute(
            text(\"SELECT id FROM workspaces WHERE workspace_id = 'ws-default'\")
        )).first()
        if row is None:
            print('  ⚠ No ws-default workspace found — skipping backfill')
            await engine.dispose()
            return
        ws_pk = row[0]

        total = 0
        for table in TABLES:
            result = await session.execute(
                text(f'UPDATE {table} SET workspace_id = :ws WHERE workspace_id IS NULL'),
                {'ws': ws_pk},
            )
            if result.rowcount > 0:
                print(f'  {table}: {result.rowcount} rows updated')
                total += result.rowcount
        await session.commit()
        if total > 0:
            print(f'  ✓ Backfilled {total} records with ws-default workspace')
        else:
            print('  ✓ All records already have workspace_id')
    await engine.dispose()

asyncio.run(backfill())
"

# 4. Run initial pipeline if no scores exist
echo "[4/5] Checking pipeline status..."
python -c "
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.scoring import RiskScore

async def check():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        count = (await session.execute(select(func.count()).select_from(RiskScore))).scalar()
    await engine.dispose()
    return count

count = asyncio.run(check())
if count == 0:
    print('  No scores found — running initial pipeline...')
    exit(0)
else:
    print(f'  {count} scores already exist — skipping pipeline')
    exit(1)
" && {
    echo "  Running initial pipeline (this may take a few minutes)..."
    python -c "
import asyncio
import httpx

async def run_pipeline():
    # Give server a moment to start
    await asyncio.sleep(2)
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            'http://localhost:8000/api/pipeline/run-full',
            json={'limit': 2000},
            timeout=300,
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f'  Pipeline complete: {data[\"total_claims\"]} claims, {data[\"cases_created\"]} cases')
        else:
            print(f'  Pipeline returned {resp.status_code} — will retry on next request')

asyncio.run(run_pipeline())
" &
    PIPELINE_PID=$!
} || echo "  ✓ Pipeline already run"

# 5. Seed governance tables from pipeline data (if pipeline has run)
echo "[5/6] Seeding governance data from pipeline results..."
python -c "
import asyncio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.config import settings
from app.models.scoring import RiskScore
from app.tao.models import AgentTrustProfile

async def check():
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        scores = (await session.execute(select(func.count()).select_from(RiskScore))).scalar()
        profiles = (await session.execute(select(func.count()).select_from(AgentTrustProfile))).scalar()
    await engine.dispose()
    return scores, profiles

scores, profiles = asyncio.run(check())
if scores > 0 and profiles == 0:
    print(f'  {scores} scores found, 0 governance profiles — seeding...')
    exit(0)
elif scores == 0:
    print('  No pipeline data yet — skipping governance seed')
    exit(1)
else:
    print(f'  Governance already seeded ({profiles} trust profiles)')
    exit(1)
" && {
    python -m app.seed.governance_data
    echo "  ✓ Governance data seeded"
} || echo "  ✓ Governance seed skipped"

# 6. Start the application (or custom command if provided)
if [ $# -gt 0 ]; then
    echo "[6/6] Starting custom command: $@"
    exec "$@"
else
    echo "[6/6] Starting uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
fi
