from __future__ import annotations

import re

from app.contracts.health_context import HealthContext
from app.contracts.recommendation import (
    ApprovedRecommendation,
    RecommendationCandidate,
    RecommendationResult,
)

_PROHIBITED = re.compile(
    r"\b("
    r"medication|medicine|prescri(?:be|ption)|dosage|dose|"
    r"stop taking|start taking|cure|treat(?:s|ment)?|reverse diabetes|"
    r"fast(?:ing)? for \d{2,}|water[- ]only|detox"
    r")\b",
    re.I,
)
_DISEASE_CLAIM = re.compile(r"\b(prevents?|eliminates?|guarantees?|will lower|will cure)\b", re.I)


class RecommendationEngine:
    """Policy gate. Candidates are never user-visible until approved here."""

    def validate(
        self,
        candidates: list[RecommendationCandidate],
        context: HealthContext,
    ) -> RecommendationResult:
        supported_codes = {
            *(m.key for m in context.markers),
            *(r.code for r in context.bio_ai_risks),
        }
        if context.scenario:
            supported_codes.update(item.code for item in context.scenario.needs_attention)
            supported_codes.update(item.code for item in context.scenario.risk_drivers)

        dietary = " ".join(context.notes + (context.lifestyle.notes if context.lifestyle else [])).lower()
        vegetarian = "vegetarian" in dietary and "non-vegetarian" not in dietary

        approved: list[ApprovedRecommendation] = []
        flags: list[str] = []
        rejected = 0
        for candidate in candidates:
            reason = self._reject_reason(candidate, supported_codes, vegetarian, context)
            if reason:
                rejected += 1
                flags.append(reason)
                continue
            approved.append(
                ApprovedRecommendation(
                    category=candidate.category,
                    text=candidate.text.strip(),
                    rationale=candidate.rationale,
                    evidence_codes=candidate.evidence_codes,
                )
            )
        return RecommendationResult(
            approved=approved[:8],
            rejected_count=rejected,
            flags=list(dict.fromkeys(flags)),
        )

    def deterministic_candidates(self, context: HealthContext) -> list[RecommendationCandidate]:
        """Conservative educational candidates grounded in available context."""
        out: list[RecommendationCandidate] = []
        keys = {m.key for m in context.markers}
        notes = " ".join(context.notes + (context.lifestyle.notes if context.lifestyle else [])).lower()
        vegetarian = "vegetarian" in notes and "non-vegetarian" not in notes

        if keys & {"ldl", "triglycerides", "cholesterol"}:
            out.extend(
                [
                    RecommendationCandidate(
                        category="foods_to_include",
                        text="Include more soluble-fibre foods such as oats, beans, lentils, fruit, and vegetables.",
                        rationale="General heart-healthy food guidance related to the available lipid results.",
                        evidence_codes=sorted(keys & {"ldl", "triglycerides", "cholesterol"}),
                    ),
                    RecommendationCandidate(
                        category="foods_to_limit",
                        text="Limit foods high in saturated fat and heavily processed foods.",
                        rationale="General heart-healthy guidance, not a treatment plan.",
                        evidence_codes=sorted(keys & {"ldl", "triglycerides", "cholesterol"}),
                    ),
                ]
            )
        if keys & {"glucose", "fasting_blood_glucose", "hba1c"}:
            out.append(
                RecommendationCandidate(
                    category="meal_patterns",
                    text="Choose regular balanced meals with vegetables, protein, fibre-rich carbohydrates, and fewer sugary drinks.",
                    rationale="General meal-pattern guidance related to the available glucose markers.",
                    evidence_codes=sorted(keys & {"glucose", "fasting_blood_glucose", "hba1c"}),
                )
            )
        if keys & {"vitamin_b12", "iron", "ferritin"}:
            foods = "lentils, beans, fortified foods, nuts, and seeds" if vegetarian else (
                "lentils, beans, eggs, fish or lean meat, and fortified foods"
            )
            out.append(
                RecommendationCandidate(
                    category="foods_to_include",
                    text=f"Discuss including suitable sources such as {foods} within your usual diet.",
                    rationale="Food-only educational guidance; supplementation requires a clinician.",
                    evidence_codes=sorted(keys & {"vitamin_b12", "iron", "ferritin"}),
                )
            )
        if context.lifestyle and context.lifestyle.activity_level:
            out.append(
                RecommendationCandidate(
                    category="activity",
                    text="Build regular, sustainable movement into the week at a level that is safe for you.",
                    rationale="General lifestyle guidance based on the available activity context.",
                    evidence_codes=["activity"],
                )
            )
        if context.lifestyle and context.lifestyle.sleep_quality:
            out.append(
                RecommendationCandidate(
                    category="sleep",
                    text="Aim for a consistent sleep schedule and discuss persistent sleep problems with a clinician.",
                    rationale="General guidance supported by the available sleep context.",
                    evidence_codes=["sleep"],
                )
            )
        if "hydration" in notes or "fluid" in notes:
            out.append(
                RecommendationCandidate(
                    category="hydration",
                    text="Maintain regular hydration unless a clinician has advised you to restrict fluids.",
                    rationale="General guidance supported by the recorded lifestyle context.",
                    evidence_codes=["nutrition"],
                )
            )
        return out

    @staticmethod
    def _reject_reason(
        candidate: RecommendationCandidate,
        supported_codes: set[str],
        vegetarian: bool,
        context: HealthContext,
    ) -> str | None:
        text = candidate.text
        if _PROHIBITED.search(text):
            return "unsafe_recommendation"
        if _DISEASE_CLAIM.search(text):
            return "unsupported_medical_claim"
        if vegetarian and re.search(r"\b(meat|fish|chicken|poultry)\b", text, re.I):
            return "dietary_constraint_conflict"
        if candidate.evidence_codes and not set(candidate.evidence_codes).issubset(
            supported_codes | {"activity", "sleep", "nutrition"}
        ):
            return "unsupported_context"
        if not candidate.evidence_codes:
            if candidate.category == "activity" and context.lifestyle and context.lifestyle.activity_level:
                return None
            if candidate.category == "sleep" and context.lifestyle and context.lifestyle.sleep_quality:
                return None
            notes = " ".join(context.notes + (context.lifestyle.notes if context.lifestyle else [])).lower()
            if candidate.category == "hydration" and any(word in notes for word in ("hydration", "fluid")):
                return None
            return "missing_recommendation_evidence"
        return None
