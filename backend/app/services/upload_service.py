"""
Upload Service — parse CSV, validate, and ingest client claims data.
"""

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace
from app.models.claim import MedicalClaim, PharmacyClaim
from app.models.provider import Provider, Pharmacy
from app.models.member import Member
from app.upload.column_maps import auto_map_columns, MEDICAL_REQUIRED, PHARMACY_REQUIRED


class UploadPreview:
    def __init__(
        self,
        *,
        total_rows: int,
        sample_rows: list[dict],
        csv_headers: list[str],
        auto_mapping: dict[str, str | None],
        unmapped_required: list[str],
    ):
        self.total_rows = total_rows
        self.sample_rows = sample_rows
        self.csv_headers = csv_headers
        self.auto_mapping = auto_mapping
        self.unmapped_required = unmapped_required

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "sample_rows": self.sample_rows[:5],
            "csv_headers": self.csv_headers,
            "auto_mapping": self.auto_mapping,
            "unmapped_required": self.unmapped_required,
        }


class ValidationResult:
    def __init__(self, *, valid_count: int, error_count: int, errors: list[dict]):
        self.valid_count = valid_count
        self.error_count = error_count
        self.errors = errors

    def to_dict(self) -> dict:
        return {
            "valid_count": self.valid_count,
            "error_count": self.error_count,
            "errors": self.errors[:50],  # cap at 50
        }


class IngestionResult:
    def __init__(
        self,
        *,
        claims_created: int,
        providers_created: int,
        members_created: int,
        pharmacies_created: int,
        batch_id: str,
        errors: list[dict],
    ):
        self.claims_created = claims_created
        self.providers_created = providers_created
        self.members_created = members_created
        self.pharmacies_created = pharmacies_created
        self.batch_id = batch_id
        self.errors = errors

    def to_dict(self) -> dict:
        return {
            "claims_created": self.claims_created,
            "providers_created": self.providers_created,
            "members_created": self.members_created,
            "pharmacies_created": self.pharmacies_created,
            "batch_id": self.batch_id,
            "error_count": len(self.errors),
            "errors": self.errors[:50],
        }


def _parse_date(val: str | None) -> date | None:
    if not val or not val.strip():
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(val: str | None) -> Decimal | None:
    if not val or not val.strip():
        return None
    try:
        cleaned = val.strip().replace(",", "").replace("$", "")
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _parse_int(val: str | None) -> int | None:
    if not val or not val.strip():
        return None
    try:
        return int(float(val.strip()))
    except (ValueError, TypeError):
        return None


def _parse_bool(val: str | None) -> bool:
    if not val:
        return False
    return val.strip().lower() in ("true", "1", "yes", "y", "t")


MAX_CSV_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_CSV_ROWS = 500_000
MAX_CSV_COLUMNS = 100

# Characters that can trigger formula injection in spreadsheet applications
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def _sanitize_cell(value: str) -> str:
    """Strip/escape special characters in a cell to prevent CSV injection."""
    if not value:
        return value
    stripped = value.strip()
    # Reject formula injection characters at cell start
    if stripped and stripped[0] in _FORMULA_PREFIXES:
        stripped = "'" + stripped
    return stripped


def validate_csv_upload(file_content: bytes) -> list[str]:
    """Pre-validate CSV upload: size, structure, no binary, no formula injection.

    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []

    # File size check
    if len(file_content) > MAX_CSV_SIZE:
        errors.append(f"File size ({len(file_content) / 1024 / 1024:.1f} MB) exceeds maximum ({MAX_CSV_SIZE / 1024 / 1024:.0f} MB)")
        return errors  # Don't parse further

    # Attempt decode — reject binary content
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        errors.append("File contains binary content and is not a valid UTF-8 CSV")
        return errors

    reader = csv.reader(io.StringIO(text))
    try:
        headers = next(reader)
    except StopIteration:
        errors.append("CSV file is empty (no header row)")
        return errors

    if len(headers) > MAX_CSV_COLUMNS:
        errors.append(f"CSV has {len(headers)} columns, maximum is {MAX_CSV_COLUMNS}")

    row_count = 0
    formula_rows: list[int] = []
    for row_num, row in enumerate(reader, start=2):
        row_count += 1
        if row_count > MAX_CSV_ROWS:
            errors.append(f"CSV has more than {MAX_CSV_ROWS:,} rows")
            break
        for cell in row:
            if cell and cell.strip() and cell.strip()[0] in _FORMULA_PREFIXES:
                formula_rows.append(row_num)
                break

    if formula_rows:
        sample = formula_rows[:5]
        errors.append(
            f"Potential CSV injection: cells starting with formula characters "
            f"(=, +, -, @) found on rows: {', '.join(str(r) for r in sample)}"
            f"{f' and {len(formula_rows) - 5} more' if len(formula_rows) > 5 else ''}"
        )

    return errors


class UploadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def preview_csv(
        self,
        file_content: bytes,
        claim_type: str = "medical",
    ) -> UploadPreview:
        """Read CSV, detect columns, auto-map, return preview."""
        text = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []

        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 99:  # read up to 100 rows for preview
                break

        # Count total rows
        text2 = file_content.decode("utf-8-sig")
        total_rows = sum(1 for _ in csv.reader(io.StringIO(text2))) - 1  # minus header

        auto_mapping = auto_map_columns(headers, claim_type)

        required = MEDICAL_REQUIRED if claim_type == "medical" else PHARMACY_REQUIRED
        unmapped = [f for f in required if auto_mapping.get(f) is None]

        return UploadPreview(
            total_rows=total_rows,
            sample_rows=rows[:5],
            csv_headers=list(headers),
            auto_mapping=auto_mapping,
            unmapped_required=unmapped,
        )

    async def ingest_medical(
        self,
        workspace: Workspace,
        file_content: bytes,
        mapping: dict[str, str],
    ) -> IngestionResult:
        """Parse CSV and insert medical claims, creating providers/members on the fly."""
        text = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        batch_id = f"UPLOAD-{uuid4().hex[:12].upper()}"

        # Cache for on-the-fly entity creation
        provider_cache: dict[str, int] = {}  # npi -> provider.id
        member_cache: dict[str, int] = {}    # member_id -> member.id

        # Pre-load existing providers/members in this workspace
        prov_result = await self.db.execute(select(Provider.npi, Provider.id))
        for row in prov_result:
            provider_cache[row[0]] = row[1]

        mem_result = await self.db.execute(select(Member.member_id, Member.id))
        for row in mem_result:
            member_cache[row[0]] = row[1]

        # Pre-load existing claim_ids to skip duplicates
        existing_claims: set[str] = set()
        ec_result = await self.db.execute(select(MedicalClaim.claim_id))
        for row in ec_result:
            existing_claims.add(row[0])

        claims_created = 0
        claims_skipped = 0
        providers_created = 0
        members_created = 0
        errors: list[dict] = []

        def _get(row: dict, field: str) -> str | None:
            csv_col = mapping.get(field)
            if not csv_col:
                return None
            return row.get(csv_col)

        for row_num, row in enumerate(reader, start=2):  # row 2 = first data row
            try:
                npi = _get(row, "provider_npi")
                member_id_str = _get(row, "member_id")
                claim_id = _get(row, "claim_id")

                if not claim_id or not member_id_str or not npi:
                    errors.append({"row": row_num, "error": "Missing required field (claim_id, member_id, or provider_npi)"})
                    continue

                # Skip duplicates
                if claim_id in existing_claims:
                    claims_skipped += 1
                    continue
                existing_claims.add(claim_id)

                # Ensure provider exists
                if npi not in provider_cache:
                    provider = Provider(
                        npi=npi,
                        name=f"Provider {npi}",
                        specialty="Unknown",
                        practice_state="XX",
                        entity_type="individual",
                        workspace_id=workspace.id,
                    )
                    self.db.add(provider)
                    await self.db.flush()
                    provider_cache[npi] = provider.id
                    providers_created += 1

                # Ensure member exists
                if member_id_str not in member_cache:
                    member = Member(
                        member_id=member_id_str,
                        first_name="Uploaded",
                        last_name=f"Member {member_id_str}",
                        date_of_birth=date(1970, 1, 1),
                        gender="M",
                        state="XX",
                        zip_code="00000",
                        plan_id="UPLOAD",
                        plan_type="Commercial",
                        eligibility_start=date(2024, 1, 1),
                        workspace_id=workspace.id,
                    )
                    self.db.add(member)
                    await self.db.flush()
                    member_cache[member_id_str] = member.id
                    members_created += 1

                service_date = _parse_date(_get(row, "service_date"))
                if not service_date:
                    errors.append({"row": row_num, "error": f"Invalid service_date: {_get(row, 'service_date')}"})
                    continue

                amount_billed = _parse_decimal(_get(row, "amount_billed"))
                if not amount_billed:
                    errors.append({"row": row_num, "error": f"Invalid amount_billed: {_get(row, 'amount_billed')}"})
                    continue

                claim = MedicalClaim(
                    claim_id=claim_id,
                    member_id=member_cache[member_id_str],
                    provider_id=provider_cache[npi],
                    service_date=service_date,
                    place_of_service=_get(row, "place_of_service") or "11",
                    claim_type=_get(row, "claim_type") or "professional",
                    cpt_code=_get(row, "cpt_code") or "99213",
                    diagnosis_code_primary=_get(row, "diagnosis_code_primary") or "Z00.00",
                    diagnosis_code_2=_get(row, "diagnosis_code_2"),
                    diagnosis_code_3=_get(row, "diagnosis_code_3"),
                    diagnosis_code_4=_get(row, "diagnosis_code_4"),
                    cpt_modifier=_get(row, "cpt_modifier"),
                    amount_billed=amount_billed,
                    amount_allowed=_parse_decimal(_get(row, "amount_allowed")),
                    amount_paid=_parse_decimal(_get(row, "amount_paid")),
                    units=_parse_int(_get(row, "units")) or 1,
                    plan_id=_get(row, "plan_id"),
                    workspace_id=workspace.id,
                    batch_id=batch_id,
                    status="received",
                )
                self.db.add(claim)
                claims_created += 1

                # Flush every 500 rows for memory efficiency
                if claims_created % 500 == 0:
                    await self.db.flush()

            except Exception as e:
                errors.append({"row": row_num, "error": str(e)})

        await self.db.flush()

        # Update workspace claim count
        workspace.claim_count = (workspace.claim_count or 0) + claims_created

        return IngestionResult(
            claims_created=claims_created,
            providers_created=providers_created,
            members_created=members_created,
            pharmacies_created=0,
            batch_id=batch_id,
            errors=errors,
        )

    async def ingest_pharmacy(
        self,
        workspace: Workspace,
        file_content: bytes,
        mapping: dict[str, str],
    ) -> IngestionResult:
        """Parse CSV and insert pharmacy claims, creating providers/pharmacies/members on the fly."""
        text = file_content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        batch_id = f"UPLOAD-{uuid4().hex[:12].upper()}"

        provider_cache: dict[str, int] = {}
        pharmacy_cache: dict[str, int] = {}
        member_cache: dict[str, int] = {}

        prov_result = await self.db.execute(select(Provider.npi, Provider.id))
        for row in prov_result:
            provider_cache[row[0]] = row[1]

        pharm_result = await self.db.execute(select(Pharmacy.npi, Pharmacy.id))
        for row in pharm_result:
            pharmacy_cache[row[0]] = row[1]

        mem_result = await self.db.execute(select(Member.member_id, Member.id))
        for row in mem_result:
            member_cache[row[0]] = row[1]

        # Pre-load existing claim_ids to skip duplicates
        existing_claims: set[str] = set()
        ec_result = await self.db.execute(select(PharmacyClaim.claim_id))
        for row in ec_result:
            existing_claims.add(row[0])

        claims_created = 0
        claims_skipped = 0
        providers_created = 0
        pharmacies_created = 0
        members_created = 0
        errors: list[dict] = []

        def _get(row: dict, field: str) -> str | None:
            csv_col = mapping.get(field)
            if not csv_col:
                return None
            return row.get(csv_col)

        for row_num, row in enumerate(reader, start=2):
            try:
                prescriber_npi = _get(row, "prescriber_npi")
                pharmacy_npi = _get(row, "pharmacy_npi")
                member_id_str = _get(row, "member_id")
                claim_id = _get(row, "claim_id")

                if not claim_id or not member_id_str or not prescriber_npi or not pharmacy_npi:
                    errors.append({"row": row_num, "error": "Missing required field"})
                    continue

                # Skip duplicates
                if claim_id in existing_claims:
                    claims_skipped += 1
                    continue
                existing_claims.add(claim_id)

                if prescriber_npi not in provider_cache:
                    prov = Provider(
                        npi=prescriber_npi, name=f"Prescriber {prescriber_npi}",
                        specialty="Unknown", practice_state="XX",
                        entity_type="individual", workspace_id=workspace.id,
                    )
                    self.db.add(prov)
                    await self.db.flush()
                    provider_cache[prescriber_npi] = prov.id
                    providers_created += 1

                if pharmacy_npi not in pharmacy_cache:
                    pharm = Pharmacy(
                        npi=pharmacy_npi, name=f"Pharmacy {pharmacy_npi}",
                        address="Unknown", city="Unknown", state="XX",
                        zip_code="00000", pharmacy_type="retail",
                        workspace_id=workspace.id,
                    )
                    self.db.add(pharm)
                    await self.db.flush()
                    pharmacy_cache[pharmacy_npi] = pharm.id
                    pharmacies_created += 1

                if member_id_str not in member_cache:
                    mem = Member(
                        member_id=member_id_str, first_name="Uploaded",
                        last_name=f"Member {member_id_str}",
                        date_of_birth=date(1970, 1, 1), gender="M",
                        state="XX", zip_code="00000", plan_id="UPLOAD",
                        plan_type="Commercial", eligibility_start=date(2024, 1, 1),
                        workspace_id=workspace.id,
                    )
                    self.db.add(mem)
                    await self.db.flush()
                    member_cache[member_id_str] = mem.id
                    members_created += 1

                fill_date = _parse_date(_get(row, "fill_date"))
                if not fill_date:
                    errors.append({"row": row_num, "error": f"Invalid fill_date"})
                    continue

                amount_billed = _parse_decimal(_get(row, "amount_billed"))
                if not amount_billed:
                    errors.append({"row": row_num, "error": f"Invalid amount_billed"})
                    continue

                claim = PharmacyClaim(
                    claim_id=claim_id,
                    member_id=member_cache[member_id_str],
                    pharmacy_id=pharmacy_cache[pharmacy_npi],
                    prescriber_id=provider_cache[prescriber_npi],
                    fill_date=fill_date,
                    ndc_code=_get(row, "ndc_code") or "00000-0000-00",
                    drug_name=_get(row, "drug_name") or "Unknown",
                    drug_class=_get(row, "drug_class"),
                    is_generic=_parse_bool(_get(row, "is_generic")),
                    is_controlled=_parse_bool(_get(row, "is_controlled")),
                    dea_schedule=_get(row, "dea_schedule"),
                    quantity_dispensed=_parse_decimal(_get(row, "quantity_dispensed")) or Decimal("30"),
                    days_supply=_parse_int(_get(row, "days_supply")) or 30,
                    refill_number=_parse_int(_get(row, "refill_number")) or 0,
                    amount_billed=amount_billed,
                    amount_allowed=_parse_decimal(_get(row, "amount_allowed")),
                    amount_paid=_parse_decimal(_get(row, "amount_paid")),
                    copay=_parse_decimal(_get(row, "copay")),
                    prescriber_npi=prescriber_npi,
                    pharmacy_npi=pharmacy_npi,
                    workspace_id=workspace.id,
                    batch_id=batch_id,
                    status="received",
                )
                self.db.add(claim)
                claims_created += 1

                if claims_created % 500 == 0:
                    await self.db.flush()

            except Exception as e:
                errors.append({"row": row_num, "error": str(e)})

        await self.db.flush()
        workspace.claim_count = (workspace.claim_count or 0) + claims_created

        return IngestionResult(
            claims_created=claims_created,
            providers_created=providers_created,
            members_created=members_created,
            pharmacies_created=pharmacies_created,
            batch_id=batch_id,
            errors=errors,
        )
