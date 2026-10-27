"""Single planner: EntityResolver + TaskPlan. Canonicalization, not a second classifier."""

from __future__ import annotations

import re

from app.contracts.common import IntentType, KnowledgeScope, QuerySource
from app.contracts.query import QueryPlan
from app.contracts.task_plan import EntityKind, QuestionType, TaskEntity, TaskOperation, TaskPlan, TaskSelector
from app.pipeline.health_domains import HealthDomainResolver, domain_for_code
from app.pipeline.lab_parameters import DERIVED_ENTITY_KEYS, FAMILY_QUERY_KEYS, display_name_for, is_lab_key, match_lab_keys
from app.pipeline.language import normalize_for_intent
from app.pipeline.ontology import match_bio_keys
from app.pipeline.operations import (
    classify_operation,
    is_falseable_change_claim,
    named_personal_sources,
    requested_item_count,
    requested_recommendation_category,
)
from app.routing.schemas import JevDecision, JevIntent, JevOperation, JevSource

_STATED_VALUE = re.compile(
    r"(mentzer(?:\s+index)?|bmi|body mass index|waist(?:\s+circumference)?)"
    r"\s+(?:is|of|=)?\s*(?:below|under|above|over)?\s*(?:about\s+)?(\d+(?:\.\d+)?)",
    re.I,
)
_CORRELATE = re.compile(
    r"\b(pattern|connected|in common|related|together|cluster|metabolic picture|consistent)\b",
    re.I,
)
_GAPS = re.compile(r"\b(missing|gaps?|what (?:information|data) is missing)\b", re.I)
_PRIORITIZE = re.compile(
    r"\b(discuss with (?:my |a )?doctor|most important|priorit|bring up with|worth attention|pay attention)\b",
    re.I,
)
_SUMMARIZE = re.compile(
    r"\b(overview|comprehensive|bigger picture|complete health|review (?:my |everything)|"
    r"all (?:my |available )?sources|summar|biggest (?:current )?health concerns)\b",
    re.I,
)
_CHANGED = re.compile(r"\b(what changed|have changed|changed over|history|which findings improved)\b", re.I)
_INTERPRET = re.compile(
    r"\b(why|explain|interpret|what does|mean|normal|ok|okay|how (?:is|are)|could explain|consistent)\b",
    re.I,
)
_EXPLAIN = re.compile(
    r"\b(measure|stand for|definition of|defined as|what is|what does .{0,20} do|"
    r"what does .{0,40} mean)\b",
    re.I,
)
_MEANING_ASK = re.compile(
    r"\b(what does .{0,48} mean|what could explain|interpret|is that (?:concerning|normal)|"
    r"are they consistent)\b",
    re.I,
)
_GROUP = re.compile(r"\b(which .{0,24}(?:related|connected)|group|abnormalities .{0,20}related)\b", re.I)
_SELECTOR_HIGH = re.compile(
    r"\b(?:which|what|any) (?:markers?|values?|results?).{0,24}\b(?:high|elevated)\b|"
    r"\b(?:high|elevated) (?:markers?|values?|results?)\b",
    re.I,
)
_SELECTOR_LOW = re.compile(
    r"\b(?:which|what|any) (?:markers?|values?|results?).{0,24}\blow\b|"
    r"\blow (?:markers?|values?|results?)\b",
    re.I,
)
_SELECTOR_ABNORMAL = re.compile(
    r"\b(abnormalit(?:y|ies)|abnormal values|out of range|flagged|worth attention)\b",
    re.I,
)
_SELECTOR_NORMAL = re.compile(r"\b(?:which|what) (?:markers?|values?).{0,16}\bnormal\b", re.I)
_SELECTOR_ALL = re.compile(r"\b(all markers|entire (?:blood )?report|every marker)\b", re.I)
_SELECTOR_CHANGED = re.compile(r"\b(which findings (?:changed|improved|worsened)|what has changed)\b", re.I)
_SELECTOR_IMPROVED = re.compile(r"\b(improved|which findings improved)\b", re.I)
_SELECTOR_WORSENED = re.compile(r"\b(worsened|got worse|which findings (?:worsened|got worse))\b", re.I)
_SELECTOR_MISSING = re.compile(r"\b(which .{0,12}missing|not tested)\b", re.I)
_SELECTOR_RELATED = re.compile(r"\b(related|connected|in common)\b", re.I)
_ENERGY = re.compile(r"\b(energy|fatigue|tired)\b", re.I)
_RECOMMEND = re.compile(
    r"\b(what should i|how (?:can|do) i|recommend|diet|eat|exercise based)\b",
    re.I,
)
_INCREASE = re.compile(
    r"\b(increased|increase|went up|risen|rose|higher than (?:last|before|previously)|got worse)\b",
    re.I,
)
_PERSONAL_LIFESTYLE_ASK = re.compile(
    r"\bhow(?:'s| is) my lifestyle\b|"
    r"\b(?:show|tell|review).{0,16}my lifestyle\b|"
    r"\bmy lifestyle\b(?!\s+changes?)",
    re.I,
)
_DOC_NARRATIVE = re.compile(
    r"\b("
    r"radiologist|impression|patholog(?:y|ist)|doctor (?:say|said|conclude)|"
    r"what did the (?:doctor|report|radiologist)|recommendation section"
    r")\b",
    re.I,
)
_DOC_SUMMARY = re.compile(
    r"\b(explain this (?:whole |entire )?report|summar(?:y|ize|ise) this (?:whole |entire )?(?:report|document))\b",
    re.I,
)
_LIST_ONLY = re.compile(
    r"\b(list only|just list|only list|without (?:an |any )?(?:explanation|interpretation)|"
    r"just (?:the |my )?results)\b",
    re.I,
)
_DECREASE = re.compile(
    r"\b(decreased|decrease|went down|fallen|fell|lower than (?:last|before|previously)|improved)\b",
    re.I,
)

_JEV_OP = {
    JevOperation.lookup: TaskOperation.retrieve,
    JevOperation.retrieve_and_explain: TaskOperation.interpret,
    JevOperation.trend: TaskOperation.trend,
    JevOperation.compare: TaskOperation.compare,
    JevOperation.summarize: TaskOperation.summarize,
    JevOperation.interpret: TaskOperation.interpret,
    JevOperation.general_answer: TaskOperation.explain,
}

_ANSWER_OP = {
    "LOOKUP": TaskOperation.retrieve,
    "EXPLAIN": TaskOperation.explain,
    "PERSONAL_INTERPRETATION": TaskOperation.interpret,
    "TREND": TaskOperation.trend,
    "COMPARE": TaskOperation.compare,
    "SUMMARIZE": TaskOperation.summarize,
    "CROSS_SOURCE_ANALYSIS": TaskOperation.correlate,
    "RECOMMEND": TaskOperation.recommend,
    "PROVENANCE": TaskOperation.provenance,
}


class EntityResolver:
    """Canonicalize mentioned entities. Health domains are not biomarkers."""

    def resolve(self, message: str) -> list[TaskEntity]:
        text = normalize_for_intent(message).lower()
        entities: list[TaskEntity] = []
        seen: set[str] = set()
        stated = {item.code: item for item in self.stated_values(message)}
        for key in match_lab_keys(text):
            if key in seen:
                continue
            seen.add(key)
            if key in FAMILY_QUERY_KEYS:
                domain = domain_for_code(key)
                entities.append(
                    TaskEntity(
                        code=domain.code if domain else key,
                        source="blood",
                        kind=EntityKind.health_domain,
                    )
                )
                continue
            source = "derived" if key in DERIVED_ENTITY_KEYS else "blood"
            kind = EntityKind.profile_attribute if key in {"bmi", "waist"} else EntityKind.biomarker
            if key in DERIVED_ENTITY_KEYS:
                kind = EntityKind.user_stated_fact if key in stated else EntityKind.biomarker
            row = stated.get(key)
            entities.append(
                TaskEntity(
                    code=key,
                    source=source,
                    kind=kind,
                    stated=bool(row),
                    stated_value=row.stated_value if row else None,
                )
            )
        for key in match_bio_keys(text):
            if key in seen:
                continue
            seen.add(key)
            domain = domain_for_code(key)
            if domain and not re.search(r"\b(scores?|bio-?ai|assessment|risks?)\b", text, re.I):
                entities.append(TaskEntity(code=domain.code, source="blood", kind=EntityKind.health_domain))
            else:
                entities.append(TaskEntity(code=key, source="bio_ai", kind=EntityKind.risk_assessment))
        for row in stated.values():
            if row.code in seen:
                continue
            seen.add(row.code)
            row.kind = EntityKind.user_stated_fact
            entities.append(row)
        return entities

    def stated_values(self, message: str) -> list[TaskEntity]:
        out: list[TaskEntity] = []
        for match in _STATED_VALUE.finditer(message or ""):
            raw = match.group(1).lower()
            if "mentzer" in raw:
                code = "mentzer"
            elif "waist" in raw:
                code = "waist"
            else:
                code = "bmi"
            try:
                value = float(match.group(2))
            except ValueError:
                value = match.group(2)
            out.append(
                TaskEntity(
                    code=code,
                    source="stated",
                    kind=EntityKind.user_stated_fact,
                    stated=True,
                    stated_value=value,
                )
            )
        return out


def infer_selectors(message: str) -> list[TaskSelector]:
    text = message or ""
    found: list[TaskSelector] = []
    if _SELECTOR_ALL.search(text):
        found.append(TaskSelector.all)
    if _SELECTOR_HIGH.search(text):
        found.append(TaskSelector.high)
    if _SELECTOR_LOW.search(text):
        found.append(TaskSelector.low)
    if _SELECTOR_ABNORMAL.search(text):
        found.append(TaskSelector.abnormal)
    if _SELECTOR_NORMAL.search(text):
        found.append(TaskSelector.normal)
    if _SELECTOR_MISSING.search(text):
        found.append(TaskSelector.missing)
    if _SELECTOR_CHANGED.search(text) or _CHANGED.search(text):
        found.append(TaskSelector.changed)
        found.append(TaskSelector.historical)
    if _SELECTOR_IMPROVED.search(text):
        found.append(TaskSelector.improved)
    if _SELECTOR_WORSENED.search(text):
        found.append(TaskSelector.worsened)
    if _SELECTOR_RELATED.search(text):
        found.append(TaskSelector.related)
    if _ENERGY.search(text):
        found.append(TaskSelector.relevant_to_goal)
    if re.search(r"\b(latest|current)\b", text, re.I) and TaskSelector.historical not in found:
        found.append(TaskSelector.latest)
    deduped: list[TaskSelector] = []
    seen: set[TaskSelector] = set()
    for item in found:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def infer_operations(plan: QueryPlan, message: str, decision: JevDecision | None = None) -> list[TaskOperation]:
    ops: list[TaskOperation] = []
    text = message or plan.raw_message or ""
    hints = {str(item).upper() for item in (getattr(plan, "operations_hint", None) or [])}
    if decision is not None:
        mapped = _JEV_OP.get(decision.operation)
        if mapped:
            ops.append(mapped)
        if decision.operation == JevOperation.retrieve_and_explain:
            ops.extend([TaskOperation.retrieve, TaskOperation.explain, TaskOperation.interpret])
        if decision.intent in {
            JevIntent.lab_result_interpretation,
            JevIntent.bio_ai_report_interpretation,
            JevIntent.questionnaire_interpretation,
        }:
            ops.append(TaskOperation.interpret)
        if decision.requires_historical_data:
            ops.append(TaskOperation.trend)
    if plan.needs_user_uploaded:
        if _DOC_SUMMARY.search(text):
            ops.append(TaskOperation.document_summary)
            ops.append(TaskOperation.interpret)
        elif _DOC_NARRATIVE.search(text):
            ops.extend([TaskOperation.document_narrative_retrieval, TaskOperation.interpret])
        elif plan.needs_cross_source:
            ops.extend(
                [
                    TaskOperation.document_structured_lookup,
                    TaskOperation.document_cross_source_compare,
                    TaskOperation.interpret,
                ]
            )
        else:
            ops.append(TaskOperation.document_structured_lookup)
    if plan.needs_personal_data:
        ops.append(TaskOperation.retrieve)
    if _CORRELATE.search(text):
        ops.extend([TaskOperation.correlate, TaskOperation.identify_pattern, TaskOperation.interpret])
    if _GROUP.search(text) or _SELECTOR_ABNORMAL.search(text) or _SELECTOR_RELATED.search(text):
        ops.append(TaskOperation.group)
    if _GAPS.search(text):
        ops.append(TaskOperation.identify_gaps)
    if plan.intent == IntentType.health_goal_progress:
        ops.append(TaskOperation.assess_goal_progress)
    if _PRIORITIZE.search(text):
        ops.append(TaskOperation.prioritize)
        if re.search(r"\bdoctor|clinician\b", text, re.I):
            ops.append(TaskOperation.prepare_clinician_discussion)
    if _SUMMARIZE.search(text) or _CHANGED.search(text):
        ops.append(TaskOperation.summarize)
    if is_falseable_change_claim(text):
        ops.extend([TaskOperation.verify_premise, TaskOperation.trend])
    if (_INTERPRET.search(text) or _MEANING_ASK.search(text)) and plan.needs_personal_data:
        ops.append(TaskOperation.interpret)
    if _MEANING_ASK.search(text) or (
        _EXPLAIN.search(text) and plan.intent.value in {"blood_marker_explanation", "bio_ai_explanation", "report_explanation"}
    ):
        ops.append(TaskOperation.explain)
        ops.append(TaskOperation.interpret)
    if _EXPLAIN.search(text) and plan.knowledge_scope == KnowledgeScope.general:
        ops.append(TaskOperation.explain)
    if _RECOMMEND.search(text):
        ops.append(TaskOperation.recommend)
    if "UPDATE_CONTEXT" in hints:
        ops.append(TaskOperation.update_context)
    if "CONTINUE_INTERPRETATION" in hints:
        ops.extend([TaskOperation.continue_interpretation, TaskOperation.interpret, TaskOperation.explain, TaskOperation.retrieve])
    if "TREND" in hints:
        ops.append(TaskOperation.trend)
    if "CORRELATE" in hints:
        ops.append(TaskOperation.correlate)
    if "INTERPRET" in hints:
        ops.append(TaskOperation.interpret)
    if "EXPLAIN" in hints:
        ops.append(TaskOperation.explain)
    if "RETRIEVE" in hints:
        ops.append(TaskOperation.retrieve)
    fallback = _ANSWER_OP.get(classify_operation(plan, text).value)
    if fallback:
        ops.append(fallback)
    deduped: list[TaskOperation] = []
    seen: set[TaskOperation] = set()
    for item in ops:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    if _LIST_ONLY.search(text):
        return [TaskOperation.retrieve]
    return deduped or [TaskOperation.retrieve]


def question_type_for(plan: QueryPlan, operations: list[TaskOperation]) -> QuestionType:
    if plan.intent in {IntentType.casual_conversation}:
        return QuestionType.general_education
    if plan.knowledge_scope == KnowledgeScope.general:
        return QuestionType.general_education
    reasoning = {
        TaskOperation.explain,
        TaskOperation.interpret,
        TaskOperation.compare,
        TaskOperation.trend,
        TaskOperation.summarize,
        TaskOperation.correlate,
        TaskOperation.group,
        TaskOperation.prioritize,
        TaskOperation.identify_gaps,
        TaskOperation.identify_pattern,
        TaskOperation.verify_premise,
        TaskOperation.recommend,
        TaskOperation.update_context,
        TaskOperation.continue_interpretation,
        TaskOperation.document_narrative_retrieval,
        TaskOperation.document_summary,
        TaskOperation.document_cross_source_compare,
    }
    if any(op in reasoning for op in operations):
        return QuestionType.personal_health_reasoning
    return QuestionType.personal_lookup


def build_task_plan(
    plan: QueryPlan,
    message: str,
    *,
    decision: JevDecision | None = None,
) -> TaskPlan:
    resolver = EntityResolver()
    entities = resolver.resolve(message)
    continuing = (plan.conversation_turn or "") in {
        "ANSWER_TO_ASSISTANT",
        "FOLLOW_UP_QUESTION",
        "REFERENCE_RESOLUTION",
        "CONFIRMATION",
        "CLARIFICATION",
        "CORRECTION",
    }
    seen = {item.code for item in entities}
    inherit = list(plan.conversation_entities or []) if continuing or not entities else []
    for code in inherit:
        if not code or code in seen:
            continue
        domain = domain_for_code(code)
        kind = EntityKind.health_domain if domain and domain.code == code else EntityKind.biomarker
        entities.append(TaskEntity(code=code, source="blood", kind=kind))
        seen.add(code)
    extra_domains = [item.code for item in entities if item.kind == EntityKind.health_domain]
    extra_domains.extend(plan.domains or [])
    for item in entities:
        mapped = domain_for_code(item.code)
        if mapped and mapped.code not in extra_domains:
            extra_domains.append(mapped.code)
    expansion = HealthDomainResolver().expand(message, extra_domain_codes=extra_domains)
    # "Why is it high?" means the one marker already in the conversation, not its whole domain.
    singular_referent = continuing and bool(plan.topic) and bool(
        re.search(r"\b(it|that|this)\b", message or "", re.I)
    ) and not bool(re.search(r"\b(they|them|those|these|and my)\b", message or "", re.I))
    selectors = infer_selectors(message)
    existing = list(plan.requested_metrics or [])
    seen = {item.code for item in entities}
    for code in expansion.domains:
        if code not in seen:
            entities.append(TaskEntity(code=code, source="blood", kind=EntityKind.health_domain))
            seen.add(code)
    primary_codes = [] if singular_referent else expansion.primary
    supporting_codes = [] if singular_referent else expansion.supporting
    optional_codes = [] if singular_referent else expansion.all_optional()
    for code in primary_codes:
        if code in FAMILY_QUERY_KEYS or code in seen:
            continue
        seen.add(code)
        entities.append(TaskEntity(code=code, source="blood", kind=EntityKind.biomarker))
    for code in supporting_codes:
        if code in seen:
            continue
        seen.add(code)
        entities.append(TaskEntity(code=code, source="blood", kind=EntityKind.biomarker, optional=True))
    for code in optional_codes:
        if code in seen:
            continue
        seen.add(code)
        entities.append(TaskEntity(code=code, source="blood", kind=EntityKind.biomarker, optional=True))
    for code in expansion.lifestyle:
        if code in seen:
            continue
        seen.add(code)
        entities.append(TaskEntity(code=code, source="questionnaire", kind=EntityKind.lifestyle_factor))
    for code in expansion.profile:
        if code in seen:
            continue
        seen.add(code)
        entities.append(
            TaskEntity(code=code, source="profile", kind=EntityKind.profile_attribute, optional=True)
        )
    for code in expansion.bioai:
        if code in seen:
            continue
        seen.add(code)
        entities.append(TaskEntity(code=code, source="bio_ai", kind=EntityKind.risk_assessment, optional=True))
    if not entities and existing:
        entities = [TaskEntity(code=code, source="blood") for code in existing]
    operations = infer_operations(plan, message, decision)
    sources: list[str] = []
    named = named_personal_sources(message)
    lifestyle_only = expansion.domains == ["lifestyle_recovery"] and "blood" not in expansion.sources
    if (plan.needs_blood or "blood" in named or "blood" in expansion.sources) and not lifestyle_only:
        sources.append("blood")
    if plan.needs_bio_ai or "bio_ai" in named or "bio_ai" in expansion.sources:
        sources.append("bio_ai")
    if plan.needs_questionnaire or "questionnaire" in named or "questionnaire" in expansion.sources:
        sources.append("questionnaire")
    if plan.needs_goals or "goals" in named or "goals" in expansion.sources:
        sources.append("goals")
    if plan.needs_profile or plan.needs_lifestyle or "profile" in expansion.sources:
        sources.append("profile")
    if plan.needs_user_uploaded or "uploaded" in named or "uploaded" in expansion.sources:
        sources.append("uploaded")
    if plan.needs_general or plan.medical_evidence_required:
        sources.append("medical")
    if expansion.virtual and "overall_health" in expansion.domains:
        for item in ("blood", "bio_ai", "questionnaire", "profile", "goals"):
            if item not in sources:
                sources.append(item)
    premise = plan.premise_claim
    if not premise and _INCREASE.search(message or ""):
        premise = "increased"
    elif not premise and _DECREASE.search(message or ""):
        premise = "decreased"
    qtype = question_type_for(plan, operations)
    history = bool(
        plan.history
        or TaskOperation.trend in operations
        or TaskOperation.compare in operations
        or TaskOperation.verify_premise in operations
        or _CHANGED.search(message or "")
        or TaskSelector.historical in selectors
    )
    dimensions = []
    if expansion.lifestyle:
        dimensions.append("lifestyle")
    if expansion.profile:
        dimensions.append("body_composition")
    mentioned = [
        item.code
        for item in entities
        if item.kind in {EntityKind.biomarker, EntityKind.profile_attribute} and not item.optional
    ]
    display = mentioned or expansion.blood_entities()
    if continuing:
        display = list(
            dict.fromkeys(
                [
                    *display,
                    *[code for code in (plan.conversation_entities or []) if is_lab_key(code)],
                ]
            )
        )
    reasoning_ctx = list(
        dict.fromkeys(
            [*expansion.optional, *expansion.derived, *expansion.lifestyle, *expansion.profile, *(plan.reasoning_context or [])]
        )
    )
    return TaskPlan(
        question_type=qtype,
        domains=list(dict.fromkeys(expansion.domains + [item.code for item in entities if item.kind == EntityKind.health_domain])),
        entities=entities,
        selectors=selectors,
        operations=operations,
        sources=list(dict.fromkeys(sources)),
        time_scope=plan.time_scope or ("historical" if history else "latest"),
        history_required=history,
        medical_evidence_required=bool(
            plan.medical_evidence_required
            or (
                qtype == QuestionType.general_education
                and plan.intent != IntentType.casual_conversation
            )
            or TaskOperation.explain in operations
            or TaskOperation.recommend in operations
        ),
        requires_personal_data=plan.needs_personal_data,
        personalization_dimensions=dimensions,
        premise_claim=premise,
        user_stated=[item for item in entities if item.stated],
        raw_message=message,
        display_entities=display,
        reasoning_context=reasoning_ctx,
    )


def attach_task_plan(plan: QueryPlan, message: str, *, decision: JevDecision | None = None) -> QueryPlan:
    """Fill TaskPlan-derived fields on QueryPlan. Does not rewrite a validated Jev source/intent."""
    task = build_task_plan(plan, message, decision=decision)
    biomarker_codes = [
        item.code
        for item in task.entities
        if item.kind in {EntityKind.biomarker, EntityKind.profile_attribute}
        and not item.optional
        and item.code not in FAMILY_QUERY_KEYS
    ]
    domain_family = []
    for code in task.domains:
        mapped = {"thyroid_health": "thyroid_function", "kidney_health": "kidney_function", "liver_health": "liver_function"}.get(code)
        if mapped:
            domain_family.append(mapped)
    risk_codes = [item.code for item in task.entities if item.kind == EntityKind.risk_assessment]
    codes = list(dict.fromkeys([*(plan.requested_metrics or []), *biomarker_codes, *domain_family, *risk_codes]))
    codes = [key for key in codes if key not in {item.code for item in task.entities if item.kind == EntityKind.health_domain}]
    codes = [
        key
        for key in codes
        if is_lab_key(key) or key in FAMILY_QUERY_KEYS or key in DERIVED_ENTITY_KEYS or key in risk_codes
    ]
    plan.requested_metrics = codes
    singular_follow_up = (plan.conversation_turn or "") in {
        "FOLLOW_UP_QUESTION",
        "REFERENCE_RESOLUTION",
    } and bool(plan.topic) and bool(re.search(r"\b(it|that|this)\b", message or "", re.I)) and not bool(
        re.search(r"\b(they|them|those|these)\b", message or "", re.I)
    )
    if singular_follow_up and is_lab_key(plan.topic):
        plan.requested_metrics = [plan.topic]
        plan.display_entities = [plan.topic]
        plan.domains = []
    plan.domains = list(task.domains)
    plan.selectors = [item.value for item in task.selectors]
    plan.optional_entities = [item.code for item in task.entities if item.optional]
    plan.display_entities = list(task.display_entities)
    plan.reasoning_context = list(dict.fromkeys([*task.reasoning_context, *(plan.reasoning_context or [])]))
    plan.operations = task.operation_values()
    plan.question_type = task.question_type.value
    if task.operations:
        primary = task.operations[0]
        if primary == TaskOperation.retrieve and len(task.operations) > 1:
            primary = next((op for op in task.operations if op != TaskOperation.retrieve), primary)
        plan.operation = {
            TaskOperation.retrieve: "LOOKUP",
            TaskOperation.explain: "EXPLAIN",
            TaskOperation.interpret: "PERSONAL_INTERPRETATION",
            TaskOperation.compare: "COMPARE",
            TaskOperation.trend: "TREND",
            TaskOperation.summarize: "SUMMARIZE",
            TaskOperation.correlate: "CROSS_SOURCE_ANALYSIS",
            TaskOperation.group: "CROSS_SOURCE_ANALYSIS",
            TaskOperation.prioritize: "SUMMARIZE",
            TaskOperation.identify_gaps: "SUMMARIZE",
            TaskOperation.identify_pattern: "PERSONAL_INTERPRETATION",
            TaskOperation.verify_premise: "TREND",
            TaskOperation.recommend: "RECOMMEND",
            TaskOperation.provenance: "PROVENANCE",
            TaskOperation.escalate: "SAFETY_ESCALATION",
            TaskOperation.update_context: "PERSONAL_INTERPRETATION",
            TaskOperation.continue_interpretation: "PERSONAL_INTERPRETATION",
            TaskOperation.assess_goal_progress: "ASSESS_GOAL_PROGRESS",
            TaskOperation.prepare_clinician_discussion: "PREPARE_CLINICIAN_DISCUSSION",
            TaskOperation.document_structured_lookup: "LOOKUP",
            TaskOperation.document_narrative_retrieval: "EXPLAIN",
            TaskOperation.document_summary: "SUMMARIZE",
            TaskOperation.document_cross_source_compare: "CROSS_SOURCE_ANALYSIS",
        }.get(primary, plan.operation or "LOOKUP")
    if task.premise_claim:
        plan.premise_claim = task.premise_claim
    if task.history_required:
        plan.history = True
        if plan.time_scope in {"none", ""}:
            plan.time_scope = "historical"
    if task.medical_evidence_required:
        plan.medical_evidence_required = True
        if plan.knowledge_scope == KnowledgeScope.general:
            plan.needs_general = True
    named = named_personal_sources(message)
    if plan.selectors and {item.upper() for item in plan.selectors} & {
        "HIGH",
        "LOW",
        "ABNORMAL",
        "ALL",
        "NORMAL",
    } and re.search(r"\b(markers?|values?|results?|report|labs?)\b", message or "", re.I):
        if not re.search(r"\b(typically|in general|what causes)\b", message or "", re.I):
            plan.knowledge_scope = KnowledgeScope.personal
            plan.needs_general = False
            if plan.intent == IntentType.general_health_question:
                plan.intent = IntentType.latest_result
    if "lifestyle_recovery" in task.domains and _PERSONAL_LIFESTYLE_ASK.search(message or ""):
        plan.knowledge_scope = KnowledgeScope.personal
        plan.needs_general = False
        if plan.intent == IntentType.general_health_question:
            plan.intent = IntentType.questionnaire_lookup
    personal = plan.knowledge_scope == KnowledgeScope.personal or plan.needs_personal_data
    # An explicitly attached upload already won source selection. Do not put the
    # same biomarker question back onto SuperShyft blood records.
    explicit_upload = bool(plan.needs_user_uploaded and not plan.needs_cross_source)
    if personal and re.search(r"\bquestionnaire\b", message or "", re.I) and not explicit_upload:
        plan.needs_questionnaire = True
        plan.needs_supershyft = True
    if personal and not explicit_upload:
        if "blood" in task.sources:
            plan.needs_blood = True
            plan.needs_supershyft = True
        elif (
            "lifestyle_recovery" in task.domains
            and "blood" not in task.sources
            and not match_lab_keys(message or "")
        ):
            plan.needs_blood = False
            plan.needs_bio_ai = False
            plan.needs_questionnaire = True
            plan.needs_lifestyle = True
            plan.needs_profile = True
        if "bio_ai" in task.sources:
            plan.needs_bio_ai = True
            plan.needs_supershyft = True
        if "questionnaire" in task.sources:
            plan.needs_questionnaire = True
        if "profile" in task.sources:
            plan.needs_profile = True
            plan.needs_lifestyle = True
        if "goals" in task.sources:
            plan.needs_goals = True
            plan.needs_profile = True
            plan.needs_supershyft = True
        if "uploaded" in task.sources:
            plan.needs_user_uploaded = True
        if "blood" in named:
            plan.needs_blood = True
            plan.needs_supershyft = True
        if "bio_ai" in named:
            plan.needs_bio_ai = True
            plan.needs_supershyft = True
        if re.search(r"\b(?:score|bio-?\s*ai)\b", message or "", re.I):
            from app.pipeline.intent import BIO_ALIASES

            for alias, code in BIO_ALIASES.items():
                if re.search(rf"\b{re.escape(alias)}\b", message or "", re.I):
                    plan.needs_bio_ai = True
                    plan.needs_supershyft = True
                    metrics = list(plan.requested_metrics or [])
                    if code not in metrics:
                        metrics.append(code)
                    plan.requested_metrics = metrics
                    break
        if "questionnaire" in named:
            plan.needs_questionnaire = True
        if "goals" in named:
            plan.needs_goals = True
            plan.needs_profile = True
            plan.needs_supershyft = True
        if "uploaded" in named:
            plan.needs_user_uploaded = True
        selector_set = {item.upper() for item in plan.selectors}
        if selector_set & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"}:
            plan.needs_blood = True
            plan.needs_supershyft = True
            if not biomarker_codes:
                plan.time_operation = "latest_report"
        if "overall_health" in task.domains:
            plan.needs_blood = True
            plan.needs_bio_ai = True
            plan.needs_questionnaire = True
            plan.needs_goals = True
            plan.needs_profile = True
            plan.needs_supershyft = True
            plan.time_operation = "latest_report"
        if len(named) >= 2 or (_SUMMARIZE.search(message or "") and personal and not named):
            if _SUMMARIZE.search(message or "") and not named:
                plan.needs_blood = True
                plan.needs_bio_ai = True
                plan.needs_questionnaire = True
                plan.needs_goals = True
            plan.needs_supershyft = True
    if len(named) >= 2:
        plan.source = QuerySource.mixed
        plan.needs_supershyft = True
        if plan.intent in {IntentType.questionnaire_lookup, IntentType.follow_up, IntentType.missing_data}:
            plan.intent = IntentType.report_explanation
            plan.time_operation = "latest_report"
            plan.history = True
    review_ops = {
        TaskOperation.summarize,
        TaskOperation.prioritize,
        TaskOperation.identify_gaps,
        TaskOperation.correlate,
    }
    if plan.intent == IntentType.missing_data and any(op in task.operations for op in review_ops):
        plan.intent = IntentType.report_explanation
        plan.time_operation = "latest_report"
        plan.history = True
        plan.needs_blood = True
        plan.needs_bio_ai = True
        plan.needs_supershyft = True
    plan.requested_category = requested_recommendation_category(message)
    plan.requested_count = requested_item_count(message)
    if task.needs_reasoning():
        plan.reasoning_required = True
    if {str(item).upper() for item in plan.selectors} & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"}:
        if not plan.requested_metrics:
            plan.time_operation = "latest_report"
            if plan.knowledge_scope == KnowledgeScope.personal:
                plan.needs_blood = True
                plan.needs_supershyft = True
    if codes and not plan.topic:
        plan.topic = codes[0]
        plan.topic_name = plan.topic_name or display_name_for(codes[0])
    from app.pipeline.presentation import infer_response_mode
    from app.contracts.health_context import HealthContext

    plan.response_mode = infer_response_mode(
        plan,
        HealthContext(
            intent=plan.intent,
            answer_depth=plan.answer_depth,
            domains=list(plan.domains or []),
        ),
        message,
    ).value
    from app.routing.model_tier import apply_answer_model_routing

    plan = apply_answer_model_routing(plan, decision=decision)
    task.complexity = plan.complexity
    task.reasoning_depth = plan.reasoning_depth
    task.model_tier = plan.model_tier or plan.answer_model_tier
    return plan


def plan_needs_reasoning(plan: QueryPlan) -> bool:
    from app.routing.model_tier import uses_medical_answer_llm

    if plan.answer_model_tier is not None and not uses_medical_answer_llm(plan.answer_model_tier):
        return False
    if plan.knowledge_scope == KnowledgeScope.general and plan.intent != IntentType.casual_conversation:
        return True
    ops = {str(item).upper() for item in (plan.operations or [])}
    if plan.operation:
        ops.add(plan.operation.upper())
    reasoning = {
        "EXPLAIN",
        "INTERPRET",
        "COMPARE",
        "TREND",
        "SUMMARIZE",
        "CORRELATE",
        "GROUP",
        "PRIORITIZE",
        "IDENTIFY_GAPS",
        "IDENTIFY_PATTERN",
        "VERIFY_PREMISE",
        "RECOMMEND",
        "CONTINUE_INTERPRETATION",
        "UPDATE_CONTEXT",
        "PERSONAL_INTERPRETATION",
        "CROSS_SOURCE_ANALYSIS",
    }
    if ops & reasoning:
        return True
    return False
