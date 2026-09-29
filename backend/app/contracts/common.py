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
