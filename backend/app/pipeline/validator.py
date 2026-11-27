"""ResponseValidator: grounding, claims, safety, and fulfillment in one place."""

from __future__ import annotations

import re

from app.contracts.health_context import HealthContext
from app.contracts.common import KnowledgeScope
from app.contracts.operations import QualityGateResult
from app.contracts.query import QueryPlan
from app.core.config import settings
from app.pipeline.claim_check import ClaimVerdict, check_claims, revise_unsupported_answer, unmapped_share
from app.pipeline.clinical_postcheck import review_clinical_output
from app.pipeline.grounding import GroundingChecker
from app.pipeline.lab_parameters import DERIVED_ENTITY_KEYS, aliases_for, display_name_for
from app.pipeline.quality_gate import review_answer
from app.pipeline.renderer import DeterministicRenderer
from app.pipeline.intent import BIO_ALIASES
from app.pipeline.safety import SafetyLayer

_BIO_CODES = set(BIO_ALIASES.values())


class ResponseValidator:
    def __init__(
        self,
        grounding: GroundingChecker | None = None,
        safety: SafetyLayer | None = None,
        renderer: DeterministicRenderer | None = None,
    ):
        self.grounding = grounding or GroundingChecker()
        self.safety = safety or SafetyLayer()
        self.renderer = renderer or DeterministicRenderer()

    def validate(
        self,
        answer: str,
        *,
        message: str,
        plan: QueryPlan,
        context: HealthContext,
        medical_hits: list | None = None,
        llm_called: bool = False,
        pre_safety=None,
    ) -> tuple[str, list[str], list[str]]:
        flags: list[str] = []
        grounding_flags: list[str] = []
        medical_hits = medical_hits or []
        if llm_called:
            unsupported = self.grounding.unsupported_number_sentences(answer, context)
            if unsupported:
                grounding_flags.append("unsupported_personal_numbers")
                answer = _drop_unsupported(answer, unsupported) or self.renderer.render(message, context)
                if not (answer or "").strip():
                    from app.pipeline.reasoning import _answer_with_stored_facts

                    answer = _answer_with_stored_facts(answer, context)
        if medical_hits:
            answer, medical_flags = self.grounding.sanitize_medical_answer(answer, medical_hits)
            grounding_flags.extend(medical_flags)
            if not plan.needs_personal_data:
                for _claim, verdict in check_claims(answer, medical_hits):
                    if verdict in {ClaimVerdict.UNSUPPORTED, ClaimVerdict.CONTRADICTED}:
                        grounding_flags.append(verdict.value.lower())
                if any(flag == "contradicted" for flag in grounding_flags):
                    answer, claim_flags = revise_unsupported_answer(answer, medical_hits)
                    grounding_flags.extend(claim_flags)
                elif llm_called and unmapped_share(answer, medical_hits) > 0.5:
                    # Most claims map to no retrieved passage: say so instead of implying a source.
                    # Flag only: the prompt asks for no "General information" label on answers.
                    grounding_flags.append("claims_unmapped")
        answer, safety_flags = self.safety.review(answer, message)
        flags.extend(safety_flags)
        if settings.cura_clinical_safety_enabled:
            answer, clinical_flags = review_clinical_output(answer, plan=plan, context=context)
            flags.extend(clinical_flags)
        if getattr(pre_safety, "flags", None):
            flags.extend(pre_safety.flags)
        gate = review_answer(answer, plan, context)
        flags.extend(gate.flags)
        coverage = _entity_coverage(answer, plan, context)
        flags.extend(coverage.flags)
        if coverage.repairs:
            flags.append("coverage_repair_withheld")
        if "backend_leak" in flags:
            answer = self.renderer.render(message, context)
        return answer, list(dict.fromkeys(flags)), list(dict.fromkeys(grounding_flags))


def _entity_coverage(answer: str, plan: QueryPlan, context: HealthContext) -> QualityGateResult:
    flags: list[str] = []
    repairs: list[str] = []
    if plan.knowledge_scope == KnowledgeScope.general or not plan.needs_personal_data:
        return QualityGateResult(passed=True, flags=flags, repairs=repairs)
    if not re.search(r"\b(my|mine)\b", plan.raw_message or "", re.I):
        return QualityGateResult(passed=True, flags=flags, repairs=repairs)
    if context.status == "ambiguous":
        # The answer asks which report to use; nothing has been looked up yet.
        return QualityGateResult(passed=True, flags=flags, repairs=repairs)
    blob = (answer or "").lower()
    if re.search(r"\bmetabolic age\b", plan.raw_message or "", re.I) and context.metabolic_age is not None:
        from app.biomarkers.metabolic_age_insight import build_metabolic_age_insight

        insight = build_metabolic_age_insight(
            actual_age=context.profile_age,
            metabolic_age=context.metabolic_age,
            assessed_on=context.bio_report_date,
        )
        if insight is not None:
            has_actual = str(insight.actual_age_years) in blob
            has_metabolic = str(insight.metabolic_age_years) in blob
            if not (has_actual and has_metabolic):
                if insight.direction == "same":
                    comparison = "the two estimates match"
                else:
                    comparison = (
                        f"the metabolic-age estimate is {abs(insight.difference_years)} "
                        f"{'year' if abs(insight.difference_years) == 1 else 'years'} {insight.direction}"
                    )
                repairs.append(
                    f"At the assessment, your actual age was estimated as {insight.actual_age_years} and "
                    f"your metabolic age was {insight.metabolic_age_years}; {comparison}."
                )
                flags.append("metabolic_age_comparison_restored")
    already_discloses_missing = any(
        token in blob
        for token in ("not available", "not present", "couldn't find", "not found", "missing")
    )
    missing_keys = {(item.key or "").lower() for item in (context.missing or [])}
    skip = {str(item).lower() for item in (plan.reasoning_context or [])} | {
        "bmi",
        "waist",
        "activity",
        "sleep",
        "diet",
        "alcohol",
        "weight",
        "height",
    }
    named = [
        item
        for item in (plan.requested_metrics or context.requested_entity_codes or [])
        if str(item).lower() not in skip
    ]
    coverage_codes = list(dict.fromkeys([*(plan.display_entities or []), *named]))
    coverage_codes = [item for item in coverage_codes if str(item).lower() not in skip]
    semantic = getattr(context, "semantic_plan", None) or {}
    if semantic:
        # Only what the member actually named must be covered. Entities added by domain
        # expansion (fasting insulin for "metabolic risk") are context, not obligations, and
        # a missing one must not be appended to a good answer.
        named_by_user = {str(c).lower() for c in [*(semantic.get("markers") or []), *(semantic.get("bio_ai") or [])]}
        present = {(m.key or "").lower() for m in context.markers}
        from app.pipeline.lab_parameters import FAMILY_QUERY_KEYS, related_keys_ordered

        glucose_family = {"glucose", "fasting_blood_glucose", "postprandial_glucose"}
        coverage_codes = [
            c for c in coverage_codes
            if str(c).lower() in named_by_user
            and not (str(c).lower() in glucose_family and present & glucose_family)
            # "my kidney" or "my thyroid" is covered by the results of that group the report holds.
            and not (str(c).lower() in FAMILY_QUERY_KEYS and present & set(related_keys_ordered(str(c).lower())))
            # "metabolic risk" resolves to the report-level score; its absence is not news.
            and str(c).lower() not in {"metabolic_score", "metabolic_age"}
        ]
    from app.pipeline.turn_kinds import spec_for

    if spec_for(getattr(context, "turn_kind", None)).skip_coverage_notes:
        # An overview turn supplies the whole record; the model decides what is relevant.
        coverage_codes = []
    for code in coverage_codes:
        name = (display_name_for(code) or code).lower()
        slug = code.replace("_", " ").lower()
        aliases = [slug, name, code.lower(), *aliases_for(code)]
        mentioned = any(alias.lower() in blob for alias in aliases if alias)
        # "my cholesterol" is answered by LDL, HDL or triglycerides; total cholesterol being absent is not news.
        if not mentioned and code.lower() in {"cholesterol", "total_cholesterol", "lipids", "lipid_profile"}:
            mentioned = any(term in blob for term in ("ldl", "hdl", "triglyceride"))
        if mentioned:
            continue
        if code.lower() in missing_keys or code in DERIVED_ENTITY_KEYS:
            if already_discloses_missing:
                flags.append("entity_missing_disclosed")
                continue
            if code.lower() not in blob and name not in blob:
                item = next((row for row in context.missing if (row.key or "").lower() == code.lower()), None)
                reason = (item.reason if item else "not found")
                repairs.append(_missing_sentence(display_name_for(code), reason))
                flags.append("entity_missing_disclosed")
            continue
        stated = any((row.fact or "").lower() == code.lower() for row in (context.user_stated or []))
        derived = any((row.fact or "").lower() == code.lower() for row in (context.derived or []))
        asked = code.lower().replace("_score", "")
        measured = any((m.key or "").lower() == code.lower() for m in context.markers) or any(
            asked == (r.code or "").lower() or asked in ((r.name or "").lower())
            for r in context.bio_ai_risks
        )
        if stated or derived or measured:
            flags.append("entity_unmentioned")
        elif not plan.needs_bio_ai and asked in _BIO_CODES:
            # The question named a Bio-AI score, but this turn did not load Bio-AI.
            # Do not tell the member the score is missing.
            flags.append("entity_unmentioned")
        else:
            repairs.append(f"{display_name_for(code)} was not found in the retrieved records.")
            flags.append("entity_undisclosed")
    return QualityGateResult(passed=not flags, flags=list(dict.fromkeys(flags)), repairs=repairs)


_MISSING_WORDS = {
    "no_reports": "is not in your reports",
    "no_report": "is not in your reports",
    "not_found": "was not found in your report",
    "not found": "was not found in your report",
    "not_reported": "was not reported",
    "no_data": "has no data in your report",
}


def _missing_sentence(name: str, reason: str) -> str:
    """A complete sentence for a missing item. A raw reason code such as no_reports is never pasted in."""
    key = (reason or "").strip().lower()
    tail = _MISSING_WORDS.get(key) or (f"was {key}" if " " in key else "was not found in your report")
    return f"{name} {tail}."


def _drop_unsupported(answer: str, unsupported: list[tuple[str, str]]) -> str | None:
    """Remove only the sentences that state an unsupported personal value.

    The member keeps the model's explanation; a value that is not in their record is never
    shown. If most of the answer is unsupported, None asks for the deterministic fallback.
    """
    from app.pipeline.grounding import to_ascii_digits

    bad = {sentence.strip() for sentence, _ in unsupported}
    text = to_ascii_digits(answer or "")
    lines = text.split("\n")
    total = kept_count = 0
    rebuilt: list[str] = []
    for line in lines:
        if not line.strip():
            rebuilt.append(line)
            continue
        sentences = re.split(r"(?<=[.!?।])\s+", line)
        kept = [s for s in sentences if s.strip() not in bad]
        total += len(sentences)
        kept_count += len(kept)
        if kept:
            rebuilt.append(" ".join(kept).strip())
    if not kept_count or kept_count < total / 2:
        return None
    return re.sub(r"\n{3,}", "\n\n", "\n".join(rebuilt)).strip()
