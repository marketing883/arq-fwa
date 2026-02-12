"""
M6: Medically Unnecessary Services Detection

Detects claims where the billed CPT procedure is not clinically appropriate
for the primary diagnosis, or where there are gender/age mismatches.
"""

from decimal import Decimal

from app.rules.base import BaseRule, RuleEvaluation
from app.services.enrichment import EnrichedMedicalClaim


class MedicallyUnnecessaryRule(BaseRule):
    """
    Flags claims where:
    1. The CPT code is NOT in the valid_cpt_codes list for the primary ICD-10 diagnosis.
    2. The diagnosis is gender-specific but the member's gender does not match.
    3. The member's age falls outside the valid age range for the diagnosis.

    Severity: gender mismatch -> 3.0, CPT-ICD mismatch -> 1.5, age mismatch -> 1.0.
    """

    rule_id = "M6"
    category = "Medically Unnecessary"
    fraud_type = "Waste"
    claim_type = "medical"
    default_weight = 7.0
    default_thresholds = {
        "require_cpt_icd_match": True,
        "check_gender": True,
        "check_age": True,
    }

    async def evaluate(
        self, claim: EnrichedMedicalClaim, thresholds: dict
    ) -> RuleEvaluation:
        check_cpt_icd = thresholds.get(
            "require_cpt_icd_match",
            self.default_thresholds["require_cpt_icd_match"],
        )
        check_gender = thresholds.get(
            "check_gender", self.default_thresholds["check_gender"]
        )
        check_age = thresholds.get(
            "check_age", self.default_thresholds["check_age"]
        )

        reasons = []
        max_severity = 0.0

        # Check gender mismatch
        if check_gender and claim.icd_gender_specific and claim.member_gender:
            if claim.icd_gender_specific != claim.member_gender:
                reasons.append(
                    f"Gender mismatch: diagnosis {claim.diagnosis_code_primary} "
                    f"is {claim.icd_gender_specific}-specific but member is {claim.member_gender}"
                )
                max_severity = max(max_severity, 3.0)

        # Check CPT-ICD mismatch
        if check_cpt_icd and claim.icd_valid_cpt_codes:
            if claim.cpt_code not in claim.icd_valid_cpt_codes:
                reasons.append(
                    f"CPT {claim.cpt_code} not valid for diagnosis "
                    f"{claim.diagnosis_code_primary} ({claim.icd_description or 'unknown'})"
                )
                max_severity = max(max_severity, 1.5)

        # Check age mismatch
        if check_age and claim.member_age is not None:
            age_mismatch = False
            if claim.icd_age_range_min is not None and claim.member_age < claim.icd_age_range_min:
                age_mismatch = True
            if claim.icd_age_range_max is not None and claim.member_age > claim.icd_age_range_max:
                age_mismatch = True

            if age_mismatch:
                reasons.append(
                    f"Age mismatch: member age {claim.member_age} outside "
                    f"range [{claim.icd_age_range_min}-{claim.icd_age_range_max}] "
                    f"for diagnosis {claim.diagnosis_code_primary}"
                )
                max_severity = max(max_severity, 1.0)

        if not reasons:
            return self._not_triggered()

        confidence = 0.85 if claim.icd_description else 0.65

        evidence = {
            "cpt_code": claim.cpt_code,
            "diagnosis": claim.diagnosis_code_primary,
            "icd_description": claim.icd_description,
            "reasons": reasons,
            "member_gender": claim.member_gender,
            "member_age": claim.member_age,
            "valid_cpt_codes": claim.icd_valid_cpt_codes[:10] if claim.icd_valid_cpt_codes else [],
            "icd_gender_specific": claim.icd_gender_specific,
            "icd_age_range": (
                f"{claim.icd_age_range_min}-{claim.icd_age_range_max}"
                if claim.icd_age_range_min is not None
                else None
            ),
        }

        details = "; ".join(reasons)

        return self._triggered(max_severity, confidence, evidence, details)
