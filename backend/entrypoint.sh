#!/bin/bash
set -e

echo "======================================"
echo "  ArqAI FWA Detection — Starting Up"
echo "======================================"

# 1. Run database migrations
echo "[1/4] Running database migrations..."
alembic upgrade head
echo "  ✓ Migrations complete"

# 2. Seed data if DB is empty
echo "[2/4] Checking seed data..."
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

# 3. Run initial pipeline if no scores exist
echo "[3/4] Checking pipeline status..."
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

# 4. Start the application
echo "[4/4] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
