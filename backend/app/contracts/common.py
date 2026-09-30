from enum import Enum


class IntentType(str, Enum):
    casual_conversation = "casual_conversation"
    latest_result = "latest_result"
    previous_result = "previous_result"
    trend = "trend"
    blood_marker_explanation = "blood_marker_explanation"
    bio_ai_score = "bio_ai_score"
    bio_ai_explanation = "bio_ai_explanation"
    bio_ai_comparison = "bio_ai_comparison"
    broad_health_summary = "broad_health_summary"
    missing_data = "missing_data"
    follow_up = "follow_up"
    general_health_question = "general_health_question"
    ambiguous_clarification = "ambiguous_clarification"
    health_scenario = "health_scenario"
    nutrition_guidance = "nutrition_guidance"
    personal_profile = "personal_profile"
    report_explanation = "report_explanation"
    health_goal_progress = "health_goal_progress"
    questionnaire_lookup = "questionnaire_lookup"


class AnswerDepth(str, Enum):
    simple = "simple"
    focused = "focused"
    broad = "broad"
    detailed = "detailed"


class QuerySource(str, Enum):
    none = "none"
    general = "general"
    blood = "blood"
    bio_ai = "bio_ai"
    lifestyle = "lifestyle"
    mixed = "mixed"
    supershyft = "supershyft"
    user_uploaded = "user_uploaded"
    questionnaire = "questionnaire"


class HealthSourceType(str, Enum):
    """First-class user-owned and knowledge sources. Jev selects; providers retrieve."""

    supershyft_blood = "supershyft_blood"
    supershyft_bio_ai = "supershyft_bio_ai"
    supershyft_questionnaire = "supershyft_questionnaire"
    supershyft_lifestyle = "supershyft_lifestyle"
    uploaded_document = "uploaded_document"
    medical_knowledge = "medical_knowledge"


class LanguageCode(str, Enum):
    auto = "auto"
    en = "en"
    hi = "hi"
    mr = "mr"
    pa = "pa"
    gu = "gu"
    bn = "bn"


class KnowledgeScope(str, Enum):
    personal = "personal"
    general = "general"


class MarkerFlag(str, Enum):
    low = "low"
    high = "high"
    critical = "critical"
    normal = "normal"
    missing = "missing"
    unknown = "unknown"


class AnswerComplexity(str, Enum):
    low = "LOW"
    medium = "MEDIUM"
    high = "HIGH"


class ReasoningDepth(str, Enum):
    none = "NONE"
    standard = "STANDARD"
    deep = "DEEP"


class AnswerModelTier(str, Enum):
    deterministic = "DETERMINISTIC"
    fast_reasoning = "FAST_REASONING"
    standard_medical = "STANDARD_MEDICAL"
    deep_medical_reasoning = "DEEP_MEDICAL_REASONING"


_COMPLEXITY_ALIASES = {
    "low": AnswerComplexity.low,
    "medium": AnswerComplexity.medium,
    "high": AnswerComplexity.high,
    "LOW": AnswerComplexity.low,
    "MEDIUM": AnswerComplexity.medium,
    "HIGH": AnswerComplexity.high,
}
_TIER_ALIASES = {
    "deterministic": AnswerModelTier.deterministic,
    "fast_reasoning": AnswerModelTier.fast_reasoning,
    "standard_medical": AnswerModelTier.standard_medical,
    "deep_medical_reasoning": AnswerModelTier.deep_medical_reasoning,
    "DETERMINISTIC": AnswerModelTier.deterministic,
    "FAST_REASONING": AnswerModelTier.fast_reasoning,
    "STANDARD_MEDICAL": AnswerModelTier.standard_medical,
    "DEEP_MEDICAL_REASONING": AnswerModelTier.deep_medical_reasoning,
    "nano": AnswerModelTier.deterministic,
    "standard": AnswerModelTier.standard_medical,
    "advanced": AnswerModelTier.deep_medical_reasoning,
}
_DEPTH_ALIASES = {
    "none": ReasoningDepth.none,
    "standard": ReasoningDepth.standard,
    "deep": ReasoningDepth.deep,
    "NONE": ReasoningDepth.none,
    "STANDARD": ReasoningDepth.standard,
    "DEEP": ReasoningDepth.deep,
}


def parse_complexity(value) -> AnswerComplexity | None:
    if value is None or value == "":
        return None
    if isinstance(value, AnswerComplexity):
        return value
    return _COMPLEXITY_ALIASES.get(str(value).strip()) or _COMPLEXITY_ALIASES.get(str(value).strip().upper())


def parse_model_tier(value) -> AnswerModelTier | None:
    if value is None or value == "":
        return None
    if isinstance(value, AnswerModelTier):
        return value
    raw = str(value).strip()
    return _TIER_ALIASES.get(raw) or _TIER_ALIASES.get(raw.upper()) or _TIER_ALIASES.get(raw.lower())


def parse_reasoning_depth(value) -> ReasoningDepth | None:
    if value is None or value == "":
        return None
    if isinstance(value, ReasoningDepth):
        return value
    raw = str(value).strip()
    return _DEPTH_ALIASES.get(raw) or _DEPTH_ALIASES.get(raw.upper()) or _DEPTH_ALIASES.get(raw.lower())
