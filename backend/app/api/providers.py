"""
Provider Peer-Comparison API — compares a single provider's billing
behaviour against specialty peers using medical claims and risk scores.
"""

from __future__ import annotations

import statistics
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, and_, distinct, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require
from app.auth.permissions import Permission
from app.auth.context import RequestContext
from app.models import Provider, MedicalClaim, RiskScore, Workspace

router = APIRouter(prefix="/api/providers", tags=["providers"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_workspace_pk(
    db: AsyncSession,
    workspace_id: str,
) -> int:
    """Translate a public workspace_id string (e.g. 'ws-xxx') to the internal PK."""
    result = await db.execute(
        select(Workspace.id).where(Workspace.workspace_id == workspace_id)
    )
    ws_pk = result.scalar()
    if ws_pk is None:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return ws_pk


def _percentile_rank(values: list[float], target: float) -> int:
    """Return the percentile (0-100) of *target* within *values*."""
    if not values:
        return 0
    count_below = sum(1 for v in values if v < target)
    count_equal = sum(1 for v in values if v == target)
    rank = (count_below + 0.5 * count_equal) / len(values) * 100
    return int(round(rank))


def _percentile(values: list[float], pct: float) -> float:
    """Return the *pct*-th percentile of *values* (0-100 scale)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (pct / 100) * (len(sorted_vals) - 1)
    f = int(k)
    c = f + 1
    if c >= len(sorted_vals):
        return sorted_vals[-1]
    d = k - f
    return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])


async def _provider_metrics(
    db: AsyncSession,
    provider_id: int,
    ws_pk: int | None,
) -> dict[str, float] | None:
    """Compute the four billing metrics for a single provider.

    Returns *None* when the provider has no qualifying claims.
    """
    filters = [MedicalClaim.provider_id == provider_id]
    if ws_pk is not None:
        filters.append(MedicalClaim.workspace_id == ws_pk)

    # --- avg_charge_per_visit ---
    avg_q = await db.execute(
        select(func.avg(MedicalClaim.amount_billed))
        .where(and_(*filters))
    )
    avg_charge = avg_q.scalar()
    if avg_charge is None:
        return None

    # --- daily_patient_volume (max claims on a single service_date) ---
    daily_subq = (
        select(
            MedicalClaim.service_date,
            func.count().label("cnt"),
        )
        .where(and_(*filters))
        .group_by(MedicalClaim.service_date)
        .subquery()
    )
    daily_q = await db.execute(
        select(func.max(daily_subq.c.cnt))
    )
    daily_max = daily_q.scalar() or 0

    # --- high_complexity_rate (fraction with cpt_code = '99215') ---
    total_q = await db.execute(
        select(func.count()).select_from(MedicalClaim).where(and_(*filters))
    )
    total_claims = total_q.scalar() or 0

    complex_q = await db.execute(
        select(func.count()).select_from(MedicalClaim).where(
            and_(*filters, MedicalClaim.cpt_code == "99215")
        )
    )
    complex_claims = complex_q.scalar() or 0
    high_complexity_rate = (
        complex_claims / total_claims if total_claims > 0 else 0.0
    )

    # --- unique_members ---
    members_q = await db.execute(
        select(func.count(distinct(MedicalClaim.member_id)))
        .where(and_(*filters))
    )
    unique_members = members_q.scalar() or 0

    return {
        "avg_charge_per_visit": round(float(avg_charge), 2),
        "daily_patient_volume": int(daily_max),
        "high_complexity_rate": round(float(high_complexity_rate), 4),
        "unique_members": int(unique_members),
    }


async def _peer_provider_ids(
    db: AsyncSession,
    specialty: str,
    ws_pk: int | None,
) -> list[int]:
    """Return provider PKs that share the given specialty."""
    filters = [Provider.specialty == specialty]
    if ws_pk is not None:
        filters.append(Provider.workspace_id == ws_pk)
    result = await db.execute(
        select(Provider.id).where(and_(*filters))
    )
    return [row[0] for row in result.all()]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

METRIC_LABELS = {
    "avg_charge_per_visit": "Avg Charge per Visit",
    "daily_patient_volume": "Daily Patient Volume",
    "high_complexity_rate": "High Complexity Rate",
    "unique_members": "Unique Members",
}


@router.get("/{npi}/peer-comparison")
async def peer_comparison(
    npi: str,
    workspace_id: str | None = Query(None),
    ctx: RequestContext = Depends(require(Permission.PROVIDERS_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Compare a provider's billing metrics to their specialty peer group."""

    # --- Resolve workspace (optional) ---
    ws_pk: int | None = None
    if workspace_id is not None:
        ws_pk = await _resolve_workspace_pk(db, workspace_id)

    # --- Look up the target provider ---
    prov_q = await db.execute(
        select(Provider).where(Provider.npi == npi)
    )
    provider = prov_q.scalar()
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Provider with NPI '{npi}' not found")

    # --- Compute provider-level metrics ---
    prov_metrics = await _provider_metrics(db, provider.id, ws_pk)
    if prov_metrics is None:
        return {
            "provider": {
                "npi": provider.npi,
                "name": provider.name,
                "specialty": provider.specialty,
            },
            "peer_group": f"{provider.specialty} (n=0)",
            "metrics": [],
        }

    # --- Peer group: all providers in the same specialty ---
    peer_ids = await _peer_provider_ids(db, provider.specialty, ws_pk)

    # Compute metrics for every peer
    peer_metrics_list: list[dict[str, float]] = []
    for pid in peer_ids:
        m = await _provider_metrics(db, pid, ws_pk)
        if m is not None:
            peer_metrics_list.append(m)

    peer_count = len(peer_metrics_list)

    # --- Build comparison for each metric ---
    metrics_output: list[dict[str, Any]] = []
    for key, label in METRIC_LABELS.items():
        provider_value = prov_metrics[key]
        peer_values = [pm[key] for pm in peer_metrics_list]

        if peer_values:
            peer_average = round(statistics.mean(peer_values), 2)
            peer_p75 = round(_percentile(peer_values, 75), 2)
            peer_p90 = round(_percentile(peer_values, 90), 2)
            percentile = _percentile_rank(peer_values, provider_value)
        else:
            peer_average = 0.0
            peer_p75 = 0.0
            peer_p90 = 0.0
            percentile = 0

        anomaly = provider_value > peer_p90 if peer_values else False

        metrics_output.append(
            {
                "metric": label,
                "provider_value": provider_value,
                "peer_average": peer_average,
                "peer_p75": peer_p75,
                "peer_p90": peer_p90,
                "percentile": percentile,
                "anomaly": anomaly,
            }
        )

    return {
        "provider": {
            "npi": provider.npi,
            "name": provider.name,
            "specialty": provider.specialty,
        },
        "peer_group": f"{provider.specialty} (n={peer_count})",
        "metrics": metrics_output,
    }
