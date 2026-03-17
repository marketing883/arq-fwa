"""
Ingestion Service — continuous data ingestion from external sources.

Supports:
  - watched_folder: scan folder for new/modified CSV files
  - api_endpoint: poll external REST API
  - database_query: run SQL query against external database
"""

import csv
import io
import json
import logging
import os
import time
from datetime import datetime
from glob import glob
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource
from app.models.ingestion_run import IngestionRun
from app.models.workspace import Workspace
from app.services.upload_service import UploadService

logger = logging.getLogger(__name__)


class IngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.upload_service = UploadService(db)

    async def poll_source(self, source: DataSource) -> IngestionRun:
        """Poll a single data source, ingest new data, optionally trigger pipeline."""
        run = IngestionRun(
            run_id=f"ING-{uuid4().hex[:12]}",
            data_source_id=source.id,
            status="running",
        )
        self.db.add(run)
        await self.db.flush()

        t_start = time.time()

        try:
            csv_bytes, new_watermark = await self._fetch_data(source)

            if csv_bytes is None:
                run.status = "no_data"
                run.duration_seconds = round(time.time() - t_start, 3)
                run.completed_at = datetime.utcnow()
                source.last_polled_at = datetime.utcnow()
                return run

            # Count rows
            reader = csv.reader(io.StringIO(csv_bytes.decode("utf-8")))
            rows = list(reader)
            run.rows_found = max(len(rows) - 1, 0)  # subtract header

            # Resolve workspace object if workspace_id is set
            workspace = None
            if source.workspace_id:
                from sqlalchemy import select

                ws_result = await self.db.execute(
                    select(Workspace).where(Workspace.id == source.workspace_id)
                )
                workspace = ws_result.scalar_one_or_none()

            if not workspace:
                # Create a minimal workspace for ingestion
                workspace = Workspace(
                    workspace_id=f"auto-ingest-{source.source_id}",
                    name=f"Auto-ingest: {source.name}",
                    data_source="ingestion",
                )
                self.db.add(workspace)
                await self.db.flush()

            # Build field mapping
            mapping = source.field_mapping if source.field_mapping else {}

            # Ingest via UploadService
            if source.claim_type == "medical":
                result = await self.upload_service.ingest_medical(
                    workspace, csv_bytes, mapping
                )
            else:
                result = await self.upload_service.ingest_pharmacy(
                    workspace, csv_bytes, mapping
                )

            run.rows_ingested = result.claims_created
            run.rows_skipped = len(result.errors)
            run.error_count = len(result.errors)
            if result.errors:
                run.errors = {"errors": result.errors[:50]}  # Cap stored errors
            run.batch_id = result.batch_id

            # Auto-trigger pipeline if configured
            if source.auto_run_pipeline and run.rows_ingested > 0:
                try:
                    from app.services.job_queue import enqueue_pipeline_job

                    job_id = await enqueue_pipeline_job(
                        workspace_id=None,  # Will process all unscored
                        limit=run.rows_ingested + 100,
                    )
                    run.pipeline_job_id = job_id
                except Exception as exc:
                    logger.warning(
                        "Failed to enqueue pipeline for source %s: %s",
                        source.source_id,
                        exc,
                    )

            run.status = "completed"
            source.last_polled_at = datetime.utcnow()
            if new_watermark:
                source.last_watermark = new_watermark

        except Exception as exc:
            logger.error(
                "Ingestion failed for source %s: %s",
                source.source_id,
                exc,
                exc_info=True,
            )
            run.status = "failed"
            run.error_count = 1
            run.errors = {"fatal": str(exc)}

        run.duration_seconds = round(time.time() - t_start, 3)
        run.completed_at = datetime.utcnow()
        return run

    async def _fetch_data(
        self, source: DataSource
    ) -> tuple[bytes | None, str | None]:
        """Dispatch to the appropriate fetcher based on source_type."""
        if source.source_type == "watched_folder":
            return await self._fetch_watched_folder(
                source.connection_config, source.last_watermark
            )
        elif source.source_type == "api_endpoint":
            return await self._fetch_api_endpoint(
                source.connection_config, source.last_watermark
            )
        elif source.source_type == "database_query":
            return await self._fetch_database_query(
                source.connection_config, source.last_watermark
            )
        else:
            raise ValueError(f"Unknown source_type: {source.source_type}")

    async def _fetch_watched_folder(
        self, config: dict, watermark: str | None
    ) -> tuple[bytes | None, str | None]:
        """Scan folder for new/modified CSV files since watermark (file mod time)."""
        folder_path = config.get("path", "")
        pattern = config.get("pattern", "*.csv")

        if not folder_path or not os.path.isdir(folder_path):
            logger.warning("Watched folder not found: %s", folder_path)
            return None, watermark

        search_pattern = os.path.join(folder_path, pattern)
        files = glob(search_pattern)

        if not files:
            return None, watermark

        # Filter files modified after watermark
        watermark_ts = float(watermark) if watermark else 0
        new_files = []
        for f in files:
            mtime = os.path.getmtime(f)
            if mtime > watermark_ts:
                new_files.append((f, mtime))

        if not new_files:
            return None, watermark

        # Sort by modification time, process all new files
        new_files.sort(key=lambda x: x[1])

        # Concatenate all new CSVs (keeping header from first file only)
        combined = io.BytesIO()
        header_written = False

        for filepath, _ in new_files:
            with open(filepath, "rb") as fh:
                lines = fh.readlines()
                if not lines:
                    continue
                if not header_written:
                    combined.write(lines[0])  # header
                    header_written = True
                for line in lines[1:]:
                    combined.write(line)

        max_mtime = max(mtime for _, mtime in new_files)
        return combined.getvalue() or None, str(max_mtime)

    async def _fetch_api_endpoint(
        self, config: dict, watermark: str | None
    ) -> tuple[bytes | None, str | None]:
        """Call external API, convert JSON response rows to CSV bytes."""
        import httpx

        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = dict(config.get("headers", {}))

        # Resolve auth token from environment
        auth_token_env = config.get("auth_token_env")
        if auth_token_env:
            token = os.environ.get(auth_token_env, "")
            auth_type = config.get("auth_type", "bearer")
            if auth_type == "bearer":
                headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "api_key":
                headers["X-API-Key"] = token

        params = dict(config.get("params", {}))
        if watermark:
            cursor_param = config.get("cursor_param", "since")
            params[cursor_param] = watermark

        async with httpx.AsyncClient(timeout=60) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers, params=params)
            else:
                resp = await client.post(
                    url, headers=headers, params=params
                )
            resp.raise_for_status()

        data = resp.json()

        # Extract rows from response
        data_path = config.get("data_path", "")
        rows = data
        if data_path:
            for key in data_path.split("."):
                rows = rows[key]

        if not rows or not isinstance(rows, list):
            return None, watermark

        # Convert JSON rows to CSV
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

        # Extract new watermark
        new_watermark = watermark
        cursor_field = config.get("cursor_field")
        if cursor_field and rows:
            new_watermark = str(rows[-1].get(cursor_field, watermark))

        return output.getvalue().encode("utf-8"), new_watermark

    async def _fetch_database_query(
        self, config: dict, watermark: str | None
    ) -> tuple[bytes | None, str | None]:
        """Run SQL query against external DB, convert result to CSV bytes."""
        from sqlalchemy import create_engine, text

        conn_string_env = config.get("connection_string_env", "")
        conn_string = os.environ.get(conn_string_env, "")
        if not conn_string:
            raise ValueError(
                f"Environment variable {conn_string_env} not set"
            )

        query = config.get("query", "")
        if not query:
            raise ValueError("No query specified in connection_config")

        # Replace watermark placeholder
        params = {}
        if watermark and ":watermark" in query:
            params["watermark"] = watermark

        engine = create_engine(conn_string)
        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            columns = list(result.keys())
            rows = result.fetchall()

        engine.dispose()

        if not rows:
            return None, watermark

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)

        # Update watermark from last row's timestamp column
        watermark_column = config.get("watermark_column")
        new_watermark = watermark
        if watermark_column and watermark_column in columns:
            idx = columns.index(watermark_column)
            new_watermark = str(rows[-1][idx])

        return output.getvalue().encode("utf-8"), new_watermark

    async def test_connection(self, source: DataSource) -> dict:
        """Test connectivity and return sample rows without ingesting."""
        try:
            csv_bytes, _ = await self._fetch_data(source)
            if csv_bytes is None:
                return {
                    "status": "ok",
                    "message": "Connected but no data found",
                    "sample_rows": [],
                }

            reader = csv.DictReader(
                io.StringIO(csv_bytes.decode("utf-8"))
            )
            sample = []
            for i, row in enumerate(reader):
                if i >= 5:
                    break
                sample.append(dict(row))

            return {
                "status": "ok",
                "message": f"Connected successfully, found data",
                "sample_rows": sample,
            }
        except Exception as exc:
            return {
                "status": "error",
                "message": str(exc),
                "sample_rows": [],
            }
