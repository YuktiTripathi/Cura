from __future__ import annotations

from dataclasses import dataclass, field

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, KnowledgeScope
from app.contracts.followup import FollowUpSuggestion
from app.contracts.health_context import HealthContext
from app.contracts.query import QueryPlan
from app.core.errors import ProviderUnavailableError
from app.db.models import Conversation
from app.providers.registry import ProviderRegistry

RELATED_MARKERS: dict[str, list[str]] = {
    "vitamin_d": ["calcium", "vitamin_b12"],
    "vitamin_b12": ["vitamin_d"],
    "hba1c": ["triglycerides", "ldl"],
    "triglycerides": ["hba1c", "ldl", "hdl"],
    "ldl": ["hdl", "triglycerides"],
    "hdl": ["ldl", "triglycerides"],
    "tsh": ["t3", "t4"],
}

MARKER_TO_BIO: dict[str, list[str]] = {
    "hba1c": ["type_2_diabetes", "metabolic_score"],
    "triglycerides": ["dyslipidemia", "type_2_diabetes", "metabolic_score"],
    "ldl": ["dyslipidemia", "cardiac_health"],
    "hdl": ["dyslipidemia", "cardiac_health"],
}

BIO_NAMES = {
    "type_2_diabetes": "metabolic risk",
    "metabolic_score": "metabolic risk",
    "dyslipidemia": "lipid-related Bio-AI assessment",
    "cardiac_health": "cardiac health assessment",
}

UNSAFE = ("medication", "prescribe", "diagnos", "start taking", "stop taking")


@dataclass
class FollowUpInventory:
    topic_result_count: int = 0
    latest_marker_keys: set[str] = field(default_factory=set)
    latest_marker_names: dict[str, str] = field(default_factory=dict)
    bio_codes: set[str] = field(default_factory=set)
    has_nutrition: bool = False
    has_lifestyle: bool = False
    sources: set[str] = field(default_factory=lambda: {"supershyft"})
    uploaded_marker_keys: set[str] = field(default_factory=set)
    discussed_intents: set[str] = field(default_factory=set)
    discussed_topics: set[str] = field(default_factory=set)
    discussed_text: list[str] = field(default_factory=list)


def _safe_query(fn, default):
    try:
        return fn()
    except ProviderUnavailableError:
        return default
    except Exception:
        return default


def build_inventory(
    principal: AuthenticatedPrincipal | None,
    registry: ProviderRegistry | None,
    plan: QueryPlan,
    conversation: Conversation | None = None,
    context: HealthContext | None = None,
) -> FollowUpInventory:
    inv = FollowUpInventory()
    if conversation is not None:
        for msg in conversation.messages or []:
            if msg.content:
                inv.discussed_text.append(msg.content.lower())
            if msg.role == "user":
                if msg.intent:
                    inv.discussed_intents.add(msg.intent)
                text = (msg.content or "").lower()
                if plan.topic and plan.topic.replace("_", " ") in text:
                    inv.discussed_topics.add(plan.topic)
        if conversation.follow_up_topic:
            inv.discussed_topics.add(conversation.follow_up_topic)

    if principal is None or registry is None:
        return inv
    if plan.knowledge_scope == KnowledgeScope.general and not getattr(plan, "needs_supershyft", False):
        return inv
    if context is not None:
        for marker in context.markers:
            inv.latest_marker_keys.add(marker.key)
            inv.latest_marker_names[marker.key] = marker.name
        inv.topic_result_count = max(
            len(context.comparisons) + (1 if context.markers else 0),
            1 if plan.topic and context.markers else 0,
        )
        inv.bio_codes.update(risk.code for risk in context.bio_ai_risks)
        if context.lifestyle:
            notes = " ".join(context.lifestyle.notes or []).lower()
            inv.has_lifestyle = bool(context.lifestyle.notes)
            inv.has_nutrition = "diet preference" in notes
        if context.data_source == "user_uploaded":
            inv.sources = {"user_uploaded"}
            inv.uploaded_marker_keys.update(marker.key for marker in context.markers)
        elif context.data_source == "cross_source":
            inv.sources = {"supershyft", "user_uploaded"}
            inv.uploaded_marker_keys.update(marker.key for marker in context.markers)
        return inv

    from app.contracts.query import QueryPlan as QP

    topic = plan.topic
    hist = QP(
        intent=IntentType.trend,
        topic=topic,
        needs_blood=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    latest = QP(
        intent=IntentType.latest_result,
        needs_blood=True,
        history=False,
        knowledge_scope=KnowledgeScope.personal,
    )
    bio_plan = QP(
        intent=IntentType.bio_ai_score,
        needs_bio_ai=True,
        history=True,
        knowledge_scope=KnowledgeScope.personal,
    )
    life_plan = QP(
        intent=IntentType.broad_health_summary,
        needs_lifestyle=True,
        knowledge_scope=KnowledgeScope.personal,
    )

    blood_hist = _safe_query(lambda: registry.blood.query(principal, hist), []) if topic else []
    inv.topic_result_count = len(blood_hist)
    latest_reports = _safe_query(lambda: registry.blood.query(principal, latest), [])
    if latest_reports:
        ordered = sorted(latest_reports, key=lambda r: (getattr(r, "report_date", None), getattr(r, "report_id", "")))
        if ordered:
            report = ordered[-1]
            for m in report.markers:
                inv.latest_marker_keys.add(m.key)
                inv.latest_marker_names[m.key] = m.name
    bio_reports = _safe_query(lambda: registry.bio_ai.query(principal, bio_plan), [])
    for report in bio_reports:
        for rk in report.risks:
            inv.bio_codes.add(rk.code)
    life = _safe_query(lambda: registry.lifestyle.query(principal, life_plan), None)
    if life:
        notes = " ".join(life.notes or []).lower()
        inv.has_lifestyle = bool(life.notes)
        inv.has_nutrition = "diet preference" in notes
    return inv


class PersonalizedFollowUpEngine:
    def generate(
        self,
        plan: QueryPlan,
        answer: str,
        context: HealthContext,
        inventory: FollowUpInventory | None = None,
        *,
        provider_unavailable: bool = False,
    ) -> list[FollowUpSuggestion]:
        if provider_unavailable:
            return []
        inv = inventory or FollowUpInventory()
        if context.status == "ambiguous":
            return self._limit(
                [
                    FollowUpSuggestion(
                        text="Would you like me to compare those Bio-AI reports?",
                        category="clarification",
                        intent="bio_ai_comparison",
                        requires_personal_context=True,
                    ),
                    FollowUpSuggestion(
                        text="Would you like to use the Bio-AI report?",
                        category="clarification",
                        intent="bio_ai_score",
                        requires_personal_context=True,
                    ),
                ]
            )

        candidates = self._candidates(plan, context, inv)
        filtered = [c for c in candidates if self._available(c, plan, context, inv)]
        filtered = [c for c in filtered if self._relevant(c, plan)]
        filtered = [c for c in filtered if self._not_discussed(c, plan, inv)]
        filtered = [c for c in filtered if self._safe(c)]
        limited = self._limit(filtered)
        scoped: list[FollowUpSuggestion] = []
        for item in limited:
            scope = "general" if not item.requires_personal_context else "personal"
            if plan.needs_cross_source and item.requires_personal_context:
                scope = "personal"
            scoped.append(item.model_copy(update={"knowledge_scope": scope}))
        return scoped

    def _candidates(self, plan: QueryPlan, context: HealthContext, inv: FollowUpInventory) -> list[FollowUpSuggestion]:
        topic = context.resolved_topic_name or plan.topic_name or "this result"
        key = plan.topic or context.resolved_topic
        personal = plan.knowledge_scope == KnowledgeScope.personal
        out: list[FollowUpSuggestion] = []

        if plan.needs_cross_source:
            key = plan.topic or context.resolved_topic
            topic = context.resolved_topic_name or plan.topic_name or "this result"
            out.append(
                    FollowUpSuggestion(
                        text=f"What does {topic} measure?",
                        category="cross_explain",
                        intent="general_health_question",
                        requires_personal_context=False,
                        source="general",
                        knowledge_scope="general",
                    )
            )
            out.append(
                FollowUpSuggestion(
                    text="Which report is newer?",
                    category="cross_newer",
                    intent="latest_result",
                    requires_personal_context=True,
                    source="mixed",
                )
            )
            for related in RELATED_MARKERS.get(key or "", []):
                if related in inv.latest_marker_keys and related in inv.uploaded_marker_keys:
                    name = inv.latest_marker_names.get(related, related.replace("_", " "))
                    out.append(
                        FollowUpSuggestion(
                            text=f"Compare {name} too",
                            category="cross_source_marker",
                            intent="latest_result",
                            requires_personal_context=True,
                            source="mixed",
                        )
                    )
            return out

        if plan.intent == IntentType.health_scenario:
            out.extend(
                [
                    FollowUpSuggestion(
                        text="Which areas in my health scenario need the most attention?",
                        category="scenario_attention",
                        intent="health_scenario",
                        requires_personal_context=True,
                    ),
                    FollowUpSuggestion(
                        text="What has changed since my previous report?",
                        category="scenario_trends",
                        intent="health_scenario",
                        requires_personal_context=True,
                    ),
                    FollowUpSuggestion(
                        text="What nutrition actions are supported by my available health context?",
                        category="scenario_nutrition",
                        intent="nutrition_guidance",
                        requires_personal_context=True,
                    ),
                ]
            )
            return out

        if plan.intent == IntentType.nutrition_guidance:
            out.extend(
                [
                    FollowUpSuggestion(
                        text="Which foods could I include more often?",
                        category="nutrition_include",
                        intent="nutrition_guidance",
                        requires_personal_context=True,
                    ),
                    FollowUpSuggestion(
                        text="Which foods could I limit based on my available context?",
                        category="nutrition_limit",
                        intent="nutrition_guidance",
                        requires_personal_context=True,
                    ),
                    FollowUpSuggestion(
                        text="How does this relate to my overall health scenario?",
                        category="nutrition_scenario",
                        intent="health_scenario",
                        requires_personal_context=True,
                    ),
                ]
            )
            return out

        if personal and key and context.markers:
            if plan.intent != IntentType.blood_marker_explanation:
                out.append(
                    FollowUpSuggestion(
                        text=f"What does my {topic} result mean?",
                        category="explanation",
                        intent="blood_marker_explanation",
                        requires_personal_context=True,
                    )
                )
            if inv.topic_result_count >= 2 and plan.intent != IntentType.trend:
                out.append(
                    FollowUpSuggestion(
                        text=f"Would you like to see how your {topic} has changed over time?",
                        category="historical_trend",
                        intent="trend",
                        requires_personal_context=True,
                    )
                )
            for related in RELATED_MARKERS.get(key or "", []):
                if related in inv.latest_marker_keys:
                    name = inv.latest_marker_names.get(related, related.replace("_", " "))
                    out.append(
                        FollowUpSuggestion(
                            text=f"Would you like me to explain how your {topic} relates to your {name} result?",
                            category="related_marker",
                            intent="latest_result",
                            requires_personal_context=True,
                        )
                    )
            for bio_code in MARKER_TO_BIO.get(key or "", []):
                if bio_code in inv.bio_codes:
                    label = BIO_NAMES.get(bio_code, "Bio-AI assessment")
                    out.append(
                        FollowUpSuggestion(
                            text=f"Would you like me to explain how your {topic} relates to your {label}?",
                            category="bio_ai_relationship",
                            intent="bio_ai_explanation",
                            requires_personal_context=True,
                        )
                    )
            if inv.has_nutrition:
                out.append(
                    FollowUpSuggestion(
                        text=f"Would you like to look at your recorded nutrition preferences alongside your {topic}?",
                        category="nutrition",
                        intent="broad_health_summary",
                        requires_personal_context=True,
                    )
                )
            elif key in {"vitamin_d", "vitamin_b12", "iron", "ldl", "triglycerides", "hba1c"}:
                out.append(
                    FollowUpSuggestion(
                        text=f"What foods are commonly discussed in relation to {topic}?",
                        category="general_foods",
                        intent="general_health_question",
                        requires_personal_context=False,
                        source="general",
                        knowledge_scope="general",
                    )
                )
            if inv.has_lifestyle and key in {"hba1c", "ldl", "triglycerides", "hdl"}:
                out.append(
                    FollowUpSuggestion(
                        text="Would you like to explore lifestyle factors that may be relevant to this result?",
                        category="lifestyle",
                        intent="bio_ai_explanation",
                        requires_personal_context=True,
                    )
                )

        if personal and plan.intent in {IntentType.bio_ai_score, IntentType.bio_ai_explanation, IntentType.bio_ai_comparison}:
            if plan.intent != IntentType.bio_ai_explanation:
                out.append(
                    FollowUpSuggestion(
                        text="Would you like me to explain what this Bio-AI assessment means?",
                        category="explanation",
                        intent="bio_ai_explanation",
                        requires_personal_context=True,
                    )
                )
            if plan.intent != IntentType.bio_ai_comparison and len(inv.bio_codes) > 0:
                out.append(
                    FollowUpSuggestion(
                        text="Would you like to compare this with your other Bio-AI report?",
                        category="comparison",
                        intent="bio_ai_comparison",
                        requires_personal_context=True,
                    )
                )

        if not personal:
            if key:
                out.append(
                    FollowUpSuggestion(
                        text=f"What does {topic} do in the body?",
                        category="explanation",
                        intent="general_health_question",
                        requires_personal_context=False,
                        source="general",
                        knowledge_scope="general",
                    )
                )
                out.append(
                    FollowUpSuggestion(
                        text=f"What are common reasons {topic} can be low or high?",
                        category="general_education",
                        intent="general_health_question",
                        requires_personal_context=False,
                        source="general",
                        knowledge_scope="general",
                    )
                )
                if key in {"ldl", "hdl", "cholesterol", "triglycerides", "hba1c"}:
                    out.append(
                        FollowUpSuggestion(
                            text=f"How can lifestyle affect {topic}?",
                            category="general_lifestyle",
                            intent="general_health_question",
                            requires_personal_context=False,
                            source="general",
                            knowledge_scope="general",
                        )
                    )
                if key in inv.latest_marker_keys:
                    out.append(
                        FollowUpSuggestion(
                            text=f"If you'd like, I can also explain what your latest {topic} result shows.",
                            category="next_action",
                            intent="latest_result",
                            requires_personal_context=True,
                        )
                    )
            elif "bio" in (plan.raw_message or "").lower():
                out.append(
                    FollowUpSuggestion(
                        text="How does a Bio-AI score differ from a medical diagnosis?",
                        category="general_education",
                        intent="general_health_question",
                        requires_personal_context=False,
                        source="general",
                        knowledge_scope="general",
                    )
                )

        if context.missing and personal and not context.markers and not context.bio_ai_risks:
            name = context.missing[0].name
            out = [
                FollowUpSuggestion(
                    text=f"What is {name}?",
                    category="general_education",
                    intent="general_health_question",
                    requires_personal_context=False,
                    source="general",
                    knowledge_scope="general",
                )
            ]
        return out

    def _available(self, item: FollowUpSuggestion, plan: QueryPlan, context: HealthContext, inv: FollowUpInventory) -> bool:
        if item.category == "historical_trend" and inv.topic_result_count < 2:
            return False
        if item.category == "bio_ai_relationship" and not inv.bio_codes:
            return False
        if item.category == "nutrition" and not inv.has_nutrition:
            return False
        if item.category == "lifestyle" and not inv.has_lifestyle:
            return False
        if item.category == "cross_source_marker":
            key = plan.topic or ""
            related = RELATED_MARKERS.get(key, [])
            if not any(r in inv.latest_marker_keys and r in inv.uploaded_marker_keys for r in related):
                return False
        if item.category == "related_marker":
            key = plan.topic or ""
            related = RELATED_MARKERS.get(key, [])
            if not any(r in inv.latest_marker_keys for r in related):
                return False
        if item.requires_personal_context and item.category == "next_action":
            key = plan.topic or ""
            if key not in inv.latest_marker_keys:
                return False
        if item.source == "user_uploaded":
            return False
        return True

    def _relevant(self, item: FollowUpSuggestion, plan: QueryPlan) -> bool:
        key = plan.topic or ""
        if item.category == "bio_ai_relationship" and key in {"vitamin_d", "vitamin_b12", "ferritin", "tsh"}:
            return False
        if item.category == "historical_trend" and plan.intent == IntentType.trend:
            return False
        if item.category == "explanation" and plan.intent in {
            IntentType.blood_marker_explanation,
            IntentType.bio_ai_explanation,
            IntentType.general_health_question,
        }:
            return False
        return True

    def _not_discussed(self, item: FollowUpSuggestion, plan: QueryPlan, inv: FollowUpInventory) -> bool:
        blob = " ".join(inv.discussed_text)
        text = item.text.lower()
        if text in blob:
            return False
        if item.intent and item.intent in inv.discussed_intents and item.category in {"explanation", "historical_trend"}:
            if item.intent == "trend" and "changed" in blob:
                return False
            if item.intent in {"blood_marker_explanation", "bio_ai_explanation"} and any(
                w in blob for w in ("why", "mean", "explain")
            ):
                return False
        if item.category == "explanation" and any(w in blob for w in ("what does", "what do", "mean", "explain")):
            if plan.knowledge_scope == KnowledgeScope.general:
                return False
        return True

    def _safe(self, item: FollowUpSuggestion) -> bool:
        lower = item.text.lower()
        return not any(token in lower for token in UNSAFE)

    def _limit(self, items: list[FollowUpSuggestion]) -> list[FollowUpSuggestion]:
        seen: set[str] = set()
        unique: list[FollowUpSuggestion] = []
        for item in items:
            if item.category in seen:
                continue
            seen.add(item.category)
            unique.append(item)
            if len(unique) >= 4:
                break
        return unique
