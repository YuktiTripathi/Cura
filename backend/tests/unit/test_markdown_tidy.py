from app.pipeline.markdown_tidy import tidy_markdown


def test_headings_are_normalised_and_spaced():
    out = tidy_markdown("### Overall Health Summary:\n- a\n# Important Findings\n- b")
    assert out == "## Overall Health Summary\n\n- a\n\n## Important Findings\n\n- b"


def test_bullets_units_and_percent_are_consistent():
    out = tidy_markdown("* **HbA1c: 6.3 %**\n• LDL 130mg/dL\n1. Glucose 98 mg / dL")
    assert out.split("\n") == ["- **HbA1c: 6.3%**", "- LDL 130 mg/dL", "- Glucose 98 mg/dL"]


def test_numbers_never_change_and_stray_bold_is_closed():
    out = tidy_markdown("- **Vitamin D: 18 ng/mL is low")
    assert "18 ng/mL" in out and out.count("**") % 2 == 0


def test_blank_runs_collapse_and_code_is_untouched():
    assert tidy_markdown("- a\n\n\n\n- b") == "- a\n\n- b"
    assert "5mg/dL" in tidy_markdown("```\n5mg/dL\n```")
    assert tidy_markdown("") == ""


def test_glued_headings_return_to_their_own_line():
    out = tidy_markdown("## Overall Health Summary\n- a. ## Important Findings\n- b. ## Reassuring Findings\n- c")
    assert out == "## Overall Health Summary\n\n- a.\n\n## Important Findings\n\n- b.\n\n## Reassuring Findings\n\n- c"


def test_report_sections_are_capped_and_other_text_is_untouched():
    from app.pipeline.markdown_tidy import cap_report_sections

    text = "## Overall Health Summary\n\n- 1\n- 2\n- 3\n\n## When to Consult a Doctor\n\n- a\n- b\n- c"
    out = cap_report_sections(text)
    assert "- 3" not in out and "- c" not in out and "- 2" in out and "- b" in out
    plain = "- one\n- two\n- three\n- four"
    assert cap_report_sections(plain) == plain


def test_sanitize_internal_ids_keeps_line_breaks():
    from app.pipeline.presentation import sanitize_internal_ids

    assert sanitize_internal_ids("## A\n\n- x\n- y") == "## A\n\n- x\n- y"


def test_friendly_text_fixes_dates_ranges_units_and_names():
    from app.pipeline.markdown_tidy import friendly_text

    out = friendly_text("LDL Cholestrol 178.8 mg/dl on 2026-09-03, sun 10–20 minutes")
    assert out == "LDL Cholesterol 178.8 mg/dL on 3 Sep 2026, sun 10 to 20 minutes"


def test_empty_headings_and_narrow_headings_are_removed():
    from app.pipeline.markdown_tidy import drop_empty_headings, strip_headings

    text = "## Plan\n\n- a\n\n## When to Consult a Doctor\n"
    assert drop_empty_headings(text) == "## Plan\n\n- a"
    assert strip_headings("## Overall Health Summary\n\n- a\n\n## Important Findings\n\n- b") == "- a\n\n- b"


def test_plain_answer_keeps_report_headings_but_strips_them_for_narrow_questions():
    from app.core.config import settings
    from app.pipeline.response_mode import plain_answer

    old = settings.cura_prompt_variant
    settings.cura_prompt_variant = "house"
    try:
        text = "## Overall Health Summary\n\n- a\n\n## Important Findings\n\n- b"
        assert "## Important Findings" in plain_answer(text, None, None, whole_report=True)
        assert "##" not in plain_answer(text, None, None, whole_report=False)
    finally:
        settings.cura_prompt_variant = old


def test_whole_report_bullets_are_capped_in_total():
    from app.pipeline.markdown_tidy import cap_total_bullets

    text = "\n".join(f"- {i}" for i in range(15))
    out = cap_total_bullets(text, 10)
    assert out.count("- ") == 10 and "- 9" in out and "- 10" not in out


def test_body_system_sections_keep_two_bullets_plus_one_and_next_steps_three():
    from app.pipeline.markdown_tidy import cap_report_sections

    text = (
        "## Blood sugar\n\n- **What the numbers show:** a\n- **What it means:** b\n- c\n- d\n\n"
        "## What to do next\n\n- 1\n- 2\n- 3\n- 4"
    )
    out = cap_report_sections(text)
    assert "- c" in out and "- d" not in out and "- 3" in out and "- 4" not in out


def test_system_headings_and_label_style_survive_tidy():
    out = tidy_markdown("### Heart and blood vessels:\n- what the numbers show: triglycerides 206 mg/dl\n- **What it means:**Fats in blood")
    assert out == "## Heart and blood vessels\n\n- triglycerides 206 mg/dl\n- Fats in blood"


def test_labels_are_bold_with_a_space_after_them():
    out = tidy_markdown("- **Looking good:**NAFLD is fine\n- what to do first: eat oats\n- **When to see a doctor**: soon")
    assert out.split("\n") == [
        "- NAFLD is fine",
        "- **What to do first:** eat oats",
        "- **When to see a doctor:** soon",
    ]


def test_spaced_hyphen_ranges_read_as_to_and_stray_dashes_go():
    from app.pipeline.markdown_tidy import friendly_text, tidy_markdown

    out = friendly_text(tidy_markdown("- Iron is 68.6 ug/dL (range 70.0 - 180.0) and low. -\n- Next."))
    assert "70.0 to 180.0" in out
    assert not out.splitlines()[0].endswith("-")


def test_leaked_field_names_are_scrubbed():
    from app.pipeline.presentation import sanitize_internal_ids

    out = sanitize_internal_ids("The member's report does not include within_range_by_body_system.")
    assert "within_range_by_body_system" not in out and "member" not in out


def test_the_limit_of_a_report_is_said_once():
    from app.pipeline.markdown_tidy import drop_repeated_limits

    text = (
        "- Oxidative stress is **53 out of 100, High**. This is a risk estimate, not a diagnosis.\n"
        "- Your liver filters blood. This pattern does not identify a disease by itself.\n"
        "- Your report can show patterns, but it cannot confirm the cause or diagnose a condition.\n"
        "- See a doctor soon."
    )
    out = drop_repeated_limits(text)
    assert out.count("risk estimate") == 1
    assert "cannot confirm" not in out and "does not identify" not in out
    assert "Your liver filters blood." in out and "See a doctor soon." in out
