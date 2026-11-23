"""Builds the guided health story for one category from facts. No model is used here.

Every value, status, date and source comes from the member's reports. Every relationship and action comes from an
approved rule. The result is a complete story on its own. A model may later add short lead lines (see story_llm).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from app.biomarkers.health_categories import category_for
from app.biomarkers.unified_overview import build_category_detail, build_unified_overview, gather
from app.contracts.unified_health import Finding
from app.health_explanation import knowledge as kb
from app.health_explanation.relationship_engine import action_library, rules
from app.health_explanation.story_schema import (
    BiomarkerCard,
    HealthStory,
    ImprovementPlan,
    LifestyleFactor,
    MeasuredFinding,
    NextSteps,
    PersonalFactors,
    PlanAction,
    RelatedCategory,
    RiskExplanation,
    Section,
    StoryMetadata,
    StoryRelationship,
    UnderstandBody,
    YourAssessment,
    YourResult,
)
from app.health_explanation.user_context import level_of

PROMPT_VERSION = "story-1"
_OUT = {"above_range", "below_range", "critical"}
_UNSUPPORTED = "This category does not have approved education text yet, so only your own results are shown."


def evidence_version(detail, lifestyle: list[LifestyleFactor]) -> str:
    """A fingerprint of everything the story states, so a cache can tell when anything changed."""
    material = {
        "f": [[f.id, f.value, f.status, f.score, f.classification, f.measured_on] for f in detail.findings],
        "l": [[x.key, x.state, x.value, x.recorded_at] for x in lifestyle],
        "kb": kb.kb_version(),
        "rules": rules()["rules_version"],
        "actions": action_library()["actions_version"],
        "prompt": PROMPT_VERSION,
    }
    return hashlib.sha256(json.dumps(material, default=str, sort_keys=True).encode()).hexdigest()[:20]


def _risk_explanations(detail, bio) -> list[RiskExplanation]:
    raw = {f"risk:{r.code}": r for r in (bio.risks if bio and bio.available else [])}
    out = []
    for f in detail.findings:
        if f.source_type != "predicted_risk" or f.status == "risk_unknown":
            continue
        r = raw.get(f.id)
        factors = list(r.contributing_factors) if r and r.contributing_factors else None
        out.append(
            RiskExplanation(
                finding_id=f.id,
                name=f.name,
                score=f.score,
                classification=f.classification or f.status_label,
                assessed_on=f.measured_on,
                what_it_means=(
                    "This is a predicted risk from your Bio-AI assessment. The score runs from 0 to 100, and a higher score places you in a higher risk group. "
                    "It estimates future risk. It is not a percentage chance."
                ),
                what_it_does_not_mean=[
                    "It is not a diagnosis.",
                    "It does not say you have, or will develop, this condition.",
                    "A score in a lower group does not rule the condition out.",
                ],
                limitations=[
                    "It is an estimate built from the information in your assessment and does not replace a medical examination.",
                    "Your report does not state which model produced it or its version.",
                ],
                contributing_factors=factors,
                contributing_note=(
                    "These factors are listed by your assessment itself."
                    if factors
                    else "Your assessment does not list contributing factors, so CURA does not guess them from your blood results."
                ),
                evidence_ids=[f"predicted:{f.id}"],
            )
        )
    return out


def _lifestyle_relationships(category_id: str, findings: list[Finding], canonical: dict[str, str | None], lifestyle: list[LifestyleFactor]) -> list[StoryRelationship]:
    out: list[StoryRelationship] = []
    for rule in rules().get("lifestyle_rules", []):
        if rule["category"] != category_id:
            continue
        level = level_of(lifestyle, rule["lifestyle"])
        if level not in rule["levels"]:
            continue
        hits = [f for f in findings if f.source_type == "measured" and canonical.get(f.id) in rule["markers"] and f.status in rule["marker_status"]]
        if not hits:
            continue
        out.append(
            StoryRelationship(
                relationship_id=f"{rule['rule_id']}:{category_id}",
                text=rule["interpretation"],
                relationship_type=rule["relationship_type"],
                finding_ids=[f.id for f in hits],
                lifestyle_keys=[rule["lifestyle"]],
                rule_id=rule["rule_id"],
                evidence_ids=[f"measured:{f.id}" for f in hits] + [f"reported:{rule['lifestyle']}"],
            )
        )
    return out


def _cards(findings: list[Finding], canonical: dict[str, str | None]) -> list[BiomarkerCard]:
    cards: list[BiomarkerCard] = []
    for f in findings:
        if f.source_type != "measured" or f.status in {"no_value"}:
            continue
        marker = kb.marker_knowledge(canonical.get(f.id))
        result = YourResult(
            value=f.value, unit=f.unit, reference_low=f.reference_low, reference_high=f.reference_high, status=f.status, status_label=f.status_label, measured_on=f.measured_on
        )
        attention = f.status in _OUT
        if marker:
            cards.append(
                BiomarkerCard(
                    marker_id=marker["marker_id"], name=marker["display_name"], finding_id=f.id, measures=marker["measures"], body_function=marker["body_function"],
                    why_it_matters=marker["why_it_matters"], causes_when_low=marker["causes_when_low"], causes_when_high=marker["causes_when_high"],
                    effects_when_low=marker["effects_when_low"], effects_when_high=marker["effects_when_high"], influences=marker["influences"],
                    practical_steps=marker["practical_steps"], related_markers=[kb.marker_knowledge(r)["display_name"] for r in marker["related_markers"] if kb.marker_knowledge(r)],
                    age_sex_note=marker["age_sex_note"], unit_note=marker["unit_note"], your_result=result, needs_attention=attention, evidence_ids=marker["evidence_ids"] + [f"measured:{f.id}"],
                    review_status=marker["review_status"],
                )
            )
        elif f.education:
            e = f.education
            cards.append(
                BiomarkerCard(
                    name=f.name, finding_id=f.id, measures=e.what_it_is, effects_when_high=e.if_high, effects_when_low=e.if_low, practical_steps=[e.next_step] if e.next_step else [],
                    your_result=result, needs_attention=attention, detail_level="basic", evidence_ids=[f"measured:{f.id}"],
                )
            )
    cards.sort(key=lambda c: (not c.needs_attention, c.name))
    return cards


def _plan(category_id: str, findings: list[Finding], canonical: dict[str, str | None], lifestyle: list[LifestyleFactor]) -> list[PlanAction]:
    out_markers = {canonical.get(f.id) for f in findings if f.source_type == "measured" and f.status in _OUT}
    raised = [f for f in findings if f.source_type == "predicted_risk" and f.status == "risk_raised"]
    any_raised = bool(out_markers or raised)
    activity, diet = level_of(lifestyle, "activity"), level_of(lifestyle, "diet")
    chosen: list[PlanAction] = []
    for a in action_library().get("story_actions", []):
        if a["category"] != category_id:
            continue
        req = a["requires"]
        if req.get("nothing_raised"):
            ok = not any_raised
        else:
            ok = bool(out_markers & set(req.get("any_marker_out", []))) or (req.get("or_risk_raised") and bool(raised))
            if "activity" in req and activity not in req["activity"]:
                ok = False
            if "diet" in req and diet not in req["diet"]:
                ok = False
        if not ok:
            continue
        support = [f"measured:{f.id}" for f in findings if f.source_type == "measured" and canonical.get(f.id) in set(req.get("any_marker_out", [])) and f.status in _OUT]
        support += [f"predicted:{f.id}" for f in raised] if req.get("or_risk_raised") else []
        if "activity" in req and activity != "not_reported":
            support.append("reported:activity")
        if "diet" in req and diet not in {"not_reported"}:
            support.append("reported:diet")
        chosen.append(PlanAction(action_id=a["action_id"], title=a["title"], what=a["what"], why=a["why"], supported_by=support, safety_note=a["safety_note"]))
    return chosen[:6]


def _monitoring(raw_rows: list, findings: list[Finding]) -> list[str]:
    out = []
    names = [f.name for f in findings if f.source_type == "measured" and f.status in _OUT]
    if names:
        shown = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1]
        out.append(f"Results to keep an eye on: {shown}. Ask your doctor whether and when they should be repeated.")
    risks = [f.name for f in findings if f.source_type == "predicted_risk" and f.status == "risk_raised"]
    if risks:
        out.append(f"Your predicted {', '.join(risks[:2])} risk is raised. Ask your doctor when your assessment should be repeated.")
    for r in raw_rows:
        if r.previous_value is not None and r.trend in {"toward_range", "away_from_range"} and r.previous_on:
            word = "closer to" if r.trend == "toward_range" else "further from"
            out.append(f"Since your earlier report on {r.previous_on}, your {r.display_name} has moved {word} the range.")
    return out[:5]


def _questions(detail, lifestyle: list[LifestyleFactor], findings: list[Finding]) -> list[str]:
    qs = [q for q in detail.follow_ups if not q.startswith(("Which foods can help", "What can I do to protect"))]
    if level_of(lifestyle, "activity") in {"low", "active"} and any(f.status in _OUT for f in findings if f.source_type == "measured"):
        qs.append("How does my activity level relate to my results?")
    if any(f.status == "risk_raised" for f in findings):
        qs.append("What is the difference between my blood results and my predicted risk?")
    seen, final = set(), []
    for q in qs:
        if q not in seen:
            seen.add(q)
            final.append(q)
    return final[:5]


def build_story(category_id: str, blood, bio, lifestyle: list[LifestyleFactor], wording=None) -> HealthStory | None:
    parts = gather(blood, bio)
    p = parts.get(category_id)
    if p is None:
        return None
    detail = build_category_detail(category_id, blood, bio, wording)
    if detail is None:
        return None
    meta = category_for(category_id)
    canonical = {r.result_id: r.canonical_id for r in p.raw_measured}
    findings = detail.findings
    edu = kb.category_education(category_id)

    understand = (
        UnderstandBody(available=True, title=edu["title"], sections=[Section(**s) for s in edu["sections"]], report_scope=edu.get("report_scope", ""), evidence_ids=edu["evidence_ids"], review_status="unreviewed")
        if edu
        else UnderstandBody(available=bool(meta.about), title=f"About your {meta.name}", sections=[Section(heading="What this covers", text=meta.about)] if meta.about else [], report_scope=_UNSUPPORTED)
    )

    measured_findings = [f for f in findings if f.source_type == "measured"]
    shown = [f for f in measured_findings if f.status != "within_range"] or []
    within = [f for f in measured_findings if f.status == "within_range"]
    shown += within[:3] if len(shown) < 4 else []
    measured = []
    for f in shown:
        m = kb.marker_knowledge(canonical.get(f.id))
        measured.append(MeasuredFinding(finding=f, marker_id=m["marker_id"] if m else None, why_relevant=(m["why_it_matters"] if m else (f.explain or "")), evidence_ids=[f"measured:{f.id}"]))

    relationships = [
        StoryRelationship(
            relationship_id=r.relationship_id, text=r.interpretation, relationship_type=r.relationship_type, finding_ids=r.finding_ids, rule_id=r.rule_id,
            evidence_status=r.evidence_status, evidence_ids=[f"rule:{r.rule_id}"] + [f"finding:{i}" for i in r.finding_ids],
        )
        for r in detail.relationships
    ] + _lifestyle_relationships(category_id, findings, canonical, lifestyle)

    missing = []
    if not measured_findings:
        missing.append("No blood results for this area are available.")
    if not any(f.source_type == "predicted_risk" for f in findings):
        missing.append("No Bio-AI risk was assessed for this area.")
    for x in lifestyle:
        if x.state == "not_reported" and x.key in {"activity", "diet", "smoking", "alcohol", "sleep", "stress"}:
            missing.append(f"{x.label} is not on record, so nothing here assumes it either way.")
    missing.append("Age, sex and family history are not used in this explanation.")

    limitations = list(detail.caveat and [detail.caveat] or [])
    if not edu:
        limitations.append(_UNSUPPORTED)
    limitations.append("The explanations and recommendations in this story are general education and have not yet been reviewed by clinicians.")
    plan_actions = _plan(category_id, findings, canonical, lifestyle)
    plan = ImprovementPlan(actions=plan_actions)

    overview = build_unified_overview(blood, bio)
    related = [RelatedCategory(id=c.id, name=c.name, status_label=c.status_label, icon=c.icon) for c in overview.categories if c.id != category_id and c.id not in {"other_unmapped", "other_risks"}][:4]

    has_blood, has_risk = bool(measured_findings), any(f.source_type == "predicted_risk" for f in findings)
    state = "complete" if has_blood and has_risk else "partial"
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return HealthStory(
        category_id=category_id,
        category_name=meta.name,
        icon=meta.icon,
        status=detail.status,
        status_label=detail.status_label,
        headline=f"Let's understand your {meta.topic}",
        understand_body=understand,
        your_assessment=YourAssessment(
            available=has_risk,
            risks=_risk_explanations(detail, bio),
            note="" if has_risk else "No Bio-AI risk was assessed for this area. This story is based on your blood results only." if has_blood else "",
        ),
        personal_factors=PersonalFactors(measured=measured, within_range_count=max(0, len(within) - sum(1 for m in measured if m.finding.status == "within_range")), lifestyle=[x for x in lifestyle if x.key in {"activity", "diet", "smoking", "alcohol", "sleep", "stress"}], relationships=relationships, missing=missing),
        biomarker_education=_cards(findings, canonical),
        improvement_plan=plan,
        next_steps=NextSteps(monitoring=_monitoring(p.raw_measured, findings), follow_ups=[], suggested_questions=_questions(detail, lifestyle, findings), related_categories=related),
        limitations=limitations,
        metadata=StoryMetadata(
            knowledge_version=kb.kb_version(), rules_version=rules()["rules_version"], actions_version=action_library()["actions_version"], prompt_version=PROMPT_VERSION,
            evidence_version=evidence_version(detail, lifestyle), generated_at=now, generation="rules", data_state=state,
        ),
    )
