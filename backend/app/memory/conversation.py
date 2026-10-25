import json
import re

from app.db.models import Conversation
from app.pipeline.operations import is_provenance_request
from app.pipeline.intent import (
    extract_topics,
    is_contextual_follow_up,
    is_educational_utterance,
    requires_personal_record,
)

ANAPHORA = re.compile(
    r"\b(it|that|this|these|those|they|them|the above|that score|that result|"
    r"the previous one|previous one|the latest one|latest one)\b",
    re.I,
)
PERSONAL_DATA_INTENTS = {
    "latest_result",
    "previous_result",
    "trend",
    "blood_marker_explanation",
    "bio_ai_score",
    "bio_ai_explanation",
    "bio_ai_comparison",
    "broad_health_summary",
    "health_scenario",
    "nutrition_guidance",
    "follow_up",
    "personal_profile",
    "report_explanation",
    "health_goal_progress",
    "questionnaire_lookup",
}


class FollowUpMemory:
    def last_user_intent(self, conversation: Conversation | None) -> str | None:
        if conversation is None:
            return None
        for msg in reversed(list(conversation.messages or [])):
            if msg.role == "user" and msg.intent:
                return msg.intent
        return None

    def prior_was_personal(self, conversation: Conversation | None) -> bool:
        intent = self.last_user_intent(conversation)
        return bool(intent and intent in PERSONAL_DATA_INTENTS)

    def last_user_message(self, conversation: Conversation | None) -> str | None:
        if conversation is None:
            return None
        for msg in reversed(list(conversation.messages or [])):
            if msg.role == "user":
                return msg.content
        return None

    def user_messages(self, conversation: Conversation | None, limit: int = 8) -> list[str]:
        """Earlier questions in this conversation, oldest first."""
        if conversation is None:
            return []
        rows = [msg.content for msg in (conversation.messages or []) if msg.role == "user" and msg.content]
        return rows[-limit:]

    def resolve_topic(self, conversation: Conversation | None, message: str) -> tuple[str | None, str | None]:
        if conversation is None:
            return None, None
        marker, bio = extract_topics(message)
        if marker or bio:
            return None, None
        from app.pipeline.questionnaire_topics import questionnaire_topic
        from app.pipeline.intent import NAMES

        q_topic = questionnaire_topic(message)
        if q_topic and conversation.follow_up_topic:
            from app.pipeline.questionnaire_intent import is_questionnaire_topic

            if is_questionnaire_topic(conversation.follow_up_topic):
                return q_topic, NAMES.get(q_topic, q_topic.replace("_", " "))
        if (
            is_educational_utterance(message)
            and not requires_personal_record(message)
            and not is_contextual_follow_up(message)
            and not is_provenance_request(message)
        ):
            return None, None
        if is_provenance_request(message) or is_contextual_follow_up(message) or ANAPHORA.search(message):
            topic, name = conversation.follow_up_topic, conversation.follow_up_topic_name
            if (topic or "") == "cholesterol" or (name or "").lower() == "cholesterol":
                return "cholesterol", "cholesterol"
            return topic, name
        return None, None

    def _persisted_state(self, conversation: Conversation | None) -> dict:
        if conversation is None or not getattr(conversation, "conversation_state_json", None):
            return {}
        try:
            state = json.loads(conversation.conversation_state_json)
            return state if isinstance(state, dict) else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    def semantic_summary(self, conversation: Conversation | None) -> str:
        """Conversation meaning only; never a source of current medical facts.

        Keep enough narrative state for the model to continue the user's health
        thread without treating remembered values as authoritative. Current lab
        values are always re-fetched by retrieval.
        """
        if conversation is None:
            return ""
        parts: list[str] = []
        state = self._persisted_state(conversation)

        if conversation.conversation_summary:
            parts.append(conversation.conversation_summary)
        topic_summary = state.get("topic_summary")
        if topic_summary:
            parts.append(f"Conversation thread: {topic_summary}")
        previous_question = state.get("previous_user_question")
        if previous_question:
            parts.append(f"Previous user question/context: {previous_question[:240]}")
        previous_answer = state.get("previous_assistant_summary")
        if previous_answer:
            parts.append(f"What CURA already explained: {previous_answer[:240]}")
        notes = [str(item).strip() for item in (state.get("recent_context_notes") or []) if str(item).strip()]
        if notes:
            parts.append("User recently mentioned: " + "; ".join(notes[-4:]))
        explained = [str(item).strip() for item in (state.get("explained_entities") or []) if str(item).strip()]
        if explained:
            parts.append("Already discussed: " + ", ".join(explained[-6:]))
        concern = state.get("current_concern")
        if concern:
            parts.append(f"Current concern: {concern}")
        goal = state.get("conversation_goal")
        if goal:
            parts.append(f"Conversation goal: {goal}")
        style = state.get("communication_style")
        if style:
            parts.append(f"Preferred response style: {style}")
        open_question = state.get("previous_assistant_follow_up")
        if open_question:
            parts.append(f"Open conversational thread: {open_question[:240]}")

        if conversation.follow_up_topic_name:
            parts.append(f"Current topic: {conversation.follow_up_topic_name}")
        if conversation.current_report_id:
            parts.append(f"Current report reference: {conversation.current_report_id}")
        if conversation.last_source_mode:
            parts.append(f"Current source mode: {conversation.last_source_mode}")
        recent_intents = [
            msg.intent
            for msg in list(conversation.messages or [])[-8:]
            if msg.role == "user" and msg.intent
        ]
        if recent_intents:
            parts.append("Recent intents: " + ", ".join(recent_intents[-4:]))
        return ". ".join(dict.fromkeys(parts))

    def updated_summary(self, conversation: Conversation, intent: str, topic_name: str | None) -> str:
        state = self._persisted_state(conversation)
        bits = []
        if topic_name:
            bits.append(f"Discussing {topic_name}")
        if state.get("current_concern"):
            bits.append(f"concern {state['current_concern']}")
        if state.get("topic_summary"):
            bits.append(str(state["topic_summary"])[:320])
        elif state.get("previous_assistant_summary"):
            bits.append(f"already explained {str(state['previous_assistant_summary'])[:240]}")
        notes = [str(item).strip() for item in (state.get("recent_context_notes") or []) if str(item).strip()]
        if notes:
            bits.append("user context " + "; ".join(notes[-3:]))
        bits.append(f"last intent {intent}")
        if conversation.last_source_mode:
            bits.append(f"source {conversation.last_source_mode}")
        return "; ".join(dict.fromkeys(bits))
