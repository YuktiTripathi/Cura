from app.pipeline.markdown_tidy import drop_routine_doctor


def test_plain_line_with_routine_doctor_sentence_does_not_crash():
    text = "Your vitamin D is 12.6 ng/mL, below the report range. Mention it at your next routine visit with your doctor."
    out = drop_routine_doctor(text)
    assert "12.6" in out
    assert "routine visit" not in out


def test_bullet_line_still_keeps_its_marker():
    out = drop_routine_doctor("- Vitamin D is low. Talk to your doctor at your next routine check.")
    assert out.startswith("- Vitamin D is low")
