from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope, MarkerFlag
from app.contracts.query import QueryPlan
from app.contracts.starters import StarterQuestion, StarterQuestionSet
from app.core.errors import ProviderUnavailableError
from app.pipeline.intent import NAMES
from app.providers.registry import ProviderRegistry

GENERAL_POOL: list[tuple[str, str]] = [
    ("vitamin_d", "What is Vitamin D and why is it important?"),
    ("hba1c", "What does HbA1c measure?"),
    ("ldl", "What causes high LDL?"),
    ("hdl", "What is the difference between HDL and LDL?"),
    ("blood_pressure", "What causes high blood pressure?"),
    ("thyroid", "How does the thyroid work?"),
    ("insulin", "What is insulin resistance?"),
    ("b12", "Why is Vitamin B12 important?"),
    ("crp", "What does CRP measure?"),
    ("liver", "What is fatty liver?"),
    ("kidney", "What do kidney function tests look at?"),
    ("heart", "What is heart health in general terms?"),
    ("metabolic", "What is metabolic age?"),
]

_PERSONAL_TEMPLATES = {
    "latest": "What is my latest {name}?",
    "meaning": "What does my {name} result mean?",
    "how": "How is my {name} level?",
    "trend": "Has my {name} changed over time?",
    "bio": "What does my {name} score mean?",
    "nutrition": "What should I know about my nutrition?",
}


def _t(kind: str, name: str) -> str:
    return _PERSONAL_TEMPLATES[kind].format(name=name)


@dataclass
class HealthSnapshot:
    available: bool = False
    markers: list = field(default_factory=list)
    marker_history: dict[str, int] = field(default_factory=dict)
    bio_risks: list = field(default_factory=list)
    has_nutrition: bool = False
    has_blood: bool = False
    has_bio: bool = False
    has_questionnaire: bool = False


def collect_snapshot(principal: AuthenticatedPrincipal, registry: ProviderRegistry) -> HealthSnapshot:
    snap = HealthSnapshot(available=True)
    blood_plan = QueryPlan(
        intent=IntentType.latest_result,
        needs_blood=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    bio_plan = QueryPlan(
        intent=IntentType.bio_ai_score,
        needs_bio_ai=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    life_plan = QueryPlan(
        intent=IntentType.broad_health_summary,
        needs_lifestyle=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    try:
        reports = registry.blood.query(principal, blood_plan) or []
    except ProviderUnavailableError:
        reports = []
        snap.available = False
    except Exception:
        reports = []
    try:
        bio = registry.bio_ai.query(principal, bio_plan) or []
    except ProviderUnavailableError:
        bio = []
        if not reports:
            snap.available = False
    except Exception:
        bio = []
    try:
        life = registry.lifestyle.query(principal, life_plan)
    except Exception:
        life = None

    ordered = sorted(reports, key=lambda r: (r.report_date, r.report_id))
    if ordered:
        snap.has_blood = True
        latest = ordered[-1]
        snap.markers = [m for m in latest.markers if m.value is not None]
        counts: dict[str, int] = {}
        for report in ordered:
            seen = {m.key for m in report.markers if m.value is not None}
            for key in seen:
                counts[key] = counts.get(key, 0) + 1
        snap.marker_history = counts
    if bio:
        snap.has_bio = True
        latest_bio = sorted(bio, key=lambda r: (r.report_date, r.report_id))[-1]
        snap.bio_risks = list(latest_bio.risks or [])
    if life and any("diet preference" in (n or "").lower() for n in (life.notes or [])):
        snap.has_nutrition = True
    try:
        provider = getattr(registry, "questionnaires", None)
        if provider is not None:
            instances = provider.query(
                principal,
                QueryPlan(
                    intent=IntentType.questionnaire_lookup,
                    needs_questionnaire=True,
                    knowledge_scope=KnowledgeScope.personal,
                ),
            ) or []
            snap.has_questionnaire = any(item.answers for item in instances)
    except Exception:
        snap.has_questionnaire = False
    return snap


def _personal_from_snapshot(snap: HealthSnapshot) -> list[StarterQuestion]:
    out: list[StarterQuestion] = []
    used: set[str] = set()

    flagged = [m for m in snap.markers if m.flag in {MarkerFlag.low, MarkerFlag.high}]
    flagged.sort(key=lambda m: m.name)
    if flagged:
        m = flagged[0]
        used.add(m.key)
        out.append(
            StarterQuestion(
                text=_t("meaning", m.name),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    others = [m for m in snap.markers if m.key not in used]
    preferred = ["hba1c", "ldl", "hdl", "vitamin_d", "tsh", "triglycerides", "vitamin_b12"]
    others.sort(key=lambda m: (preferred.index(m.key) if m.key in preferred else 99, m.name))
    if others and len(out) < 3:
        m = others[0]
        used.add(m.key)
        kind = "how" if m.key in {"ldl", "hdl", "triglycerides"} else "latest"
        out.append(
            StarterQuestion(
                text=_t(kind, m.name),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    trend_keys = [k for k, n in snap.marker_history.items() if n >= 2 and k not in used]
    if trend_keys and len(out) < 3:
        key = trend_keys[0]
        name = next((m.name for m in snap.markers if m.key == key), NAMES.get(key, key.replace("_", " ")))
        used.add(key)
        out.append(
            StarterQuestion(
                text=_t("trend", name),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    if snap.bio_risks and len(out) < 3:
        risk = next((r for r in snap.bio_risks if r.code == "cardiac_health"), snap.bio_risks[0])
        name = risk.name or NAMES.get(risk.code or "", "Bio-AI")
        out.append(
            StarterQuestion(
                text=_t("bio", name),
                knowledge_scope="personal",
                category="personal_health",
            )
        )

    if snap.has_nutrition and len(out) < 3:
        out.append(
            StarterQuestion(
                text=_PERSONAL_TEMPLATES["nutrition"],
                knowledge_scope="personal",
                category="personal_health",
            )
        )
    return out[:3]


def _general_questions(seed: str, avoid: set[str], count: int) -> list[StarterQuestion]:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    start = int(digest[:8], 16) % len(GENERAL_POOL)
    ordered = GENERAL_POOL[start:] + GENERAL_POOL[:start]
    out: list[StarterQuestion] = []
    for key, _en in ordered:
        if key in avoid and len(out) + (count - len(out)) > 0 and any(k not in avoid for k, _ in ordered):
            if key in avoid:
                continue
        text = _en
        out.append(
            StarterQuestion(
                text=text,
                knowledge_scope="general",
                category="general_education",
            )
        )
        if len(out) >= count:
            break
    if len(out) < count:
        for key, _en in ordered:
            text = _en
            if any(q.text == text for q in out):
                continue
            out.append(
                StarterQuestion(text=text, knowledge_scope="general", category="general_education")
            )
            if len(out) >= count:
                break
    return out[:count]


def build_starters(
    principal: AuthenticatedPrincipal,
    registry: ProviderRegistry,
    language: str | None = None,  # ignored; starters are English
    *,
    snapshot: HealthSnapshot | None = None,
    profile_available: bool = True,
) -> StarterQuestionSet:
    if not profile_available:
        generals = _general_questions(str(principal.subject_id) + ":down", set(), 2)
        return StarterQuestionSet(personal=[], general=generals, personal_unavailable=True)

    snap = snapshot if snapshot is not None else collect_snapshot(principal, registry)
    if not snap.available and not snap.has_blood and not snap.has_bio:
        generals = _general_questions(str(principal.subject_id) + ":empty", set(), 2)
        return StarterQuestionSet(personal=[], general=generals, personal_unavailable=True)

    personal = _personal_from_snapshot(snap)
    avoid = {m.key for m in snap.markers}
    extra = max(0, 3 - len(personal))
    generals = _general_questions(str(principal.subject_id), avoid, 2 + extra)
    return StarterQuestionSet(
        personal=personal,
        general=generals,
        personal_unavailable=len(personal) == 0,
    )
