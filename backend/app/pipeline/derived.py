"""Deterministic derived metrics. Not question-specific."""

from __future__ import annotations

from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.health_context import HealthContext, MissingItem
from app.contracts.query import QueryPlan
from app.pipeline.lab_parameters import display_name_for


def attach_derived_facts(context: HealthContext, plan: QueryPlan | None = None) -> HealthContext:
    derived: list[ProvenancedFact] = list(context.derived or [])
    existing = {(item.fact or "").lower() for item in derived}
    mentzer = _mentzer_index(context)
    if mentzer is not None and "mentzer" not in existing:
        derived.append(mentzer)
        existing.add("mentzer")
    bmi = _bmi(context)
    if bmi is not None and "bmi" not in existing:
        derived.append(bmi)
    context.derived = derived
    if derived:
        facts = list(context.facts or [])
        present = {(item.fact or "").lower() for item in facts}
        for row in derived:
            if (row.fact or "").lower() not in present:
                facts.append(row)
        context.facts = facts
    requested = set((plan.requested_metrics if plan else None) or context.requested_entity_codes or [])
    if "mentzer" in requested and not any((item.fact or "").lower() == "mentzer" for item in derived):
        if not any((item.fact or "").lower() == "mentzer" for item in (context.user_stated or [])):
            if not any((item.key or "").lower() == "mentzer" for item in context.missing):
                context.missing.append(
                    MissingItem(
                        key="mentzer",
                        name=display_name_for("mentzer"),
                        reason="not_computable",
                        scope="derived from MCV and RBC",
                    )
                )
    return context


def attach_user_stated(context: HealthContext, plan: QueryPlan) -> HealthContext:
    from app.pipeline.planner import EntityResolver

    stated = EntityResolver().stated_values(plan.raw_message or "")
    rows: list[ProvenancedFact] = list(context.user_stated or [])
    existing = {(item.fact or "").lower() for item in rows}
    for item in stated:
        if item.code in existing:
            continue
        rows.append(
            ProvenancedFact(
                fact=item.code,
                value=item.stated_value,
                source="user_message",
                fact_type=FactKind.user_stated_health_information,
                notes=["User-stated; not a retrieved laboratory measurement"],
                source_type="user_stated",
            )
        )
    context.user_stated = rows
    if rows:
        facts = list(context.facts or [])
        facts.extend(rows)
        context.facts = facts
    return context


def _marker_value(context: HealthContext, key: str) -> tuple[float | None, ProvenancedFact | None]:
    for marker in context.markers:
        if (marker.key or "").lower() == key and marker.value is not None:
            return float(marker.value), None
    for fact in context.facts or []:
        if (fact.fact or "").lower() == key and isinstance(fact.value, (int, float)):
            return float(fact.value), fact
    return None, None


def _mentzer_index(context: HealthContext) -> ProvenancedFact | None:
    mcv, _ = _marker_value(context, "mcv")
    rbc, _ = _marker_value(context, "rbc")
    if mcv is None or rbc is None or rbc == 0:
        return None
    value = round(mcv / rbc, 2)
    mcv_marker = next((m for m in context.markers if m.key == "mcv"), None)
    return ProvenancedFact(
        fact="mentzer",
        value=value,
        unit="index",
        source="derived",
        report_id=mcv_marker.report_id if mcv_marker else None,
        measured_at=mcv_marker.measured_at if mcv_marker else None,
        fact_type=FactKind.measured_personal_fact,
        notes=[f"Computed as MCV/RBC ({mcv}/{rbc})"],
        source_type="derived",
        confidence="high",
    )


def _bmi(context: HealthContext) -> ProvenancedFact | None:
    height = None
    weight = None
    for fact in list(context.facts or []) + list(getattr(context.profile, "lifestyle", None) or []):
        key = (getattr(fact, "fact", None) or "").lower()
        if key in {"height", "height_cm"} and isinstance(fact.value, (int, float)):
            height = float(fact.value)
        if key in {"weight", "weight_kg"} and isinstance(fact.value, (int, float)):
            weight = float(fact.value)
    if height is None or weight is None or height <= 0:
        return None
    metres = height / 100 if height > 3 else height
    if metres <= 0:
        return None
    value = round(weight / (metres * metres), 1)
    return ProvenancedFact(
        fact="bmi",
        value=value,
        unit="kg/m2",
        source="derived",
        fact_type=FactKind.measured_personal_fact,
        notes=["Computed from stored height and weight"],
        source_type="derived",
        confidence="high",
    )
