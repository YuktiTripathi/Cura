import re
from dataclasses import dataclass

from app.contracts.common import MarkerFlag
from app.contracts.health_context import HealthContext

DIAGNOSIS = re.compile(r"\b(you have|diagnosed with|this confirms|this proves you)\b", re.I)
MEDICATION = re.compile(r"\b(take \d+ mg|prescribe|dosage of|start metformin|take insulin)\b", re.I)
EMERGENCY = re.compile(r"\b(call 911|emergency department immediately|you are having a heart attack)\b", re.I)
IMPROVED = re.compile(r"\b(your (health|diabetes) (improved|got worse)|this confirms diabetes)\b", re.I)
UNSAFE_REQUEST = re.compile(
    r"(do i have diabetes|what disease i have|definitely cancer|stop my (medicine|medication)|"
    r"double my dose|ignore (your |the )?safety|prescribe treatment|ignore previous instructions)",
    re.I,
)
URGENT_REQUEST = re.compile(
    r"\b(chest pain|difficulty breathing|shortness of breath|unconscious|"
    r"severe bleeding|stroke symptoms|suicid(?:e|al)|overdose)\b",
    re.I,
)
DOSAGE_REQUEST = re.compile(
    r"\b(what dose|how many (?:mg|tablets)|increase my dose|decrease my dose|"
    r"double my dose|dosage|stop (?:taking |my )|start (?:taking |my ))\b",
    re.I,
)
DIAGNOSIS_REQUEST = re.compile(
    r"\b(do i have|have i got|am i diabetic|what disease do i have|diagnose me)\b",
    re.I,
)
PROMPT_INJECTION = re.compile(
    r"\b(ignore previous|ignore your|reveal (?:the )?(?:system|prompt)|"
    r"developer message|bypass safety|act as an? unrestricted)\b",
    re.I,
)
OUT_OF_SCOPE = re.compile(r"\b(build malware|steal password|hack account)\b", re.I)


@dataclass
class PreSafetyDecision:
    blocked: bool = False
    answer: str | None = None
    flags: list[str] | None = None
    escalation: str | None = None


class SafetyLayer:
    def check_input(self, user_message: str) -> PreSafetyDecision:
        flags: list[str] = []
        if PROMPT_INJECTION.search(user_message):
            flags.append("prompt_injection")
            return PreSafetyDecision(
                blocked=True,
                answer="I can help with health questions, but I can't follow instructions that try to override Cura's safety or privacy rules.",
                flags=flags,
            )
        if URGENT_REQUEST.search(user_message):
            flags.append("urgent_symptoms")
            return PreSafetyDecision(
                blocked=True,
                answer=(
                    "This may need urgent medical attention. Contact your local emergency service or seek urgent in-person care now. "
                    "Cura cannot assess emergencies."
                ),
                flags=flags,
                escalation="urgent_care",
            )
        if DOSAGE_REQUEST.search(user_message):
            flags.append("medication_or_dosage_request")
            return PreSafetyDecision(
                blocked=True,
                answer=(
                    "I can't recommend medication doses or tell you to start, stop, or change medicine. "
                    "Please contact the clinician or pharmacist managing your medication."
                ),
                flags=flags,
                escalation="clinician",
            )
        if DIAGNOSIS_REQUEST.search(user_message):
            flags.append("diagnosis_request")
            return PreSafetyDecision(
                blocked=True,
                answer=(
                    "I can't diagnose a condition from symptoms or reports. "
                    "I can explain your measured results and risk assessments, and you should discuss diagnosis with a clinician."
                ),
                flags=flags,
                escalation="clinician",
            )
        if OUT_OF_SCOPE.search(user_message):
            flags.append("out_of_scope")
            return PreSafetyDecision(
                blocked=True,
                answer="I can only help with Cura's supported health-education and health-report questions.",
                flags=flags,
            )
        return PreSafetyDecision(flags=flags)

    def scan_critical_context(self, context: HealthContext) -> tuple[list[str], str | None]:
        critical = [m.name for m in context.markers if m.flag == MarkerFlag.critical]
        if not critical:
            return [], None
        return ["critical_value"], "urgent_clinician_review"

    def review(self, answer: str, user_message: str | None = None) -> tuple[str, list[str]]:
        flags: list[str] = []
        out = answer
        if DIAGNOSIS.search(answer):
            flags.append("diagnosis_language")
            out += "\n\nThis is not a diagnosis. Discuss results with a clinician."
        if MEDICATION.search(answer):
            flags.append("medication_recommendation")
            out = re.sub(MEDICATION, "[medication advice removed]", out)
            out += "\n\nI cannot recommend medications or dosages."
        if EMERGENCY.search(answer):
            flags.append("emergency_language")
        if IMPROVED.search(answer):
            flags.append("clinical_judgment")
            out += "\n\nA value difference is not by itself an assessment of improvement or worsening."
        if user_message and UNSAFE_REQUEST.search(user_message):
            flags.append("unsafe_user_request")
            out += (
                "\n\nI can't diagnose, prescribe, or change medication. "
                "Please discuss your results with a clinician."
            )
        return out, flags
