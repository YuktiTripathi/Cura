from app.contracts.bio_ai import BioAIRisk
from app.contracts.common import AnswerDepth, IntentType, KnowledgeScope
from app.contracts.health_context import HealthContext
from app.pipeline.renderer import DeterministicRenderer, format_bio_ai_risk_line, render_bio_ai_ambiguity, render_bio_ai_score_list


def test_bio_ai_line_uses_parentheses_not_dash():
    line = format_bio_ai_risk_line(
        BioAIRisk(code="hypertension", name="Hypertension", score=16, status="Healthy")
    )
    assert line == "• **Hypertension:** 16 (Healthy)"
    assert "—" not in line
    assert "–" not in line
    assert ";" not in line
    assert "|" not in line


def test_missing_score_is_not_none_healthy():
    line = format_bio_ai_risk_line(
        BioAIRisk(code="thyroid", name="Thyroid Health", score=None, status="Healthy")
    )
    assert line == "• **Thyroid Health:** No score reported"
    assert "None" not in line


def test_structured_bio_ai_report_layout():
    text = render_bio_ai_score_list(
        [
            BioAIRisk(code="hypertension", name="Hypertension", score=16.0, status="Healthy"),
            BioAIRisk(code="nafld", name="NAFLD", score=13, status="Healthy"),
            BioAIRisk(code="thyroid", name="Thyroid Health", score=None, status="Healthy"),
        ]
    )
    assert text.startswith("Your Bio-AI Report")
    assert "Your latest Bio-AI assessment shows:" in text
    assert "• **Hypertension:** 16 (Healthy)" in text
    assert "• **NAFLD:** 13 (Healthy)" in text
    assert "• **Thyroid Health:** No score reported" in text
    assert "These scores are from your Bio-AI assessment and are not a medical diagnosis." in text
    assert "—" not in text
    assert "supershyft" not in text.lower()
    assert "Source:" not in text


def test_renderer_uses_structured_bio_ai_list():
    ctx = HealthContext(
        intent=IntentType.bio_ai_score,
        answer_depth=AnswerDepth.simple,
        knowledge_scope=KnowledgeScope.personal,
        bio_ai_risks=[
            BioAIRisk(code="cardiac_health", name="Cardiac Health", score=10, status="Healthy"),
        ],
    )
    answer = DeterministicRenderer().render("Explain my latest Bio-AI report", ctx)
    assert "• **Cardiac Health:** 10 (Healthy)" in answer
    assert "—" not in answer
