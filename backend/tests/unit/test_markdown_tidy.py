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

    text = "## Overall Health Summary\n\n- 1\n- 2\n- 3\n\n## When to Consult a Doctor\n\n- a\n- b"
    out = cap_report_sections(text)
    assert "- 3" not in out and "- b" not in out and "- 2" in out
    plain = "- one\n- two\n- three\n- four"
    assert cap_report_sections(plain) == plain


def test_sanitize_internal_ids_keeps_line_breaks():
    from app.pipeline.presentation import sanitize_internal_ids

    assert sanitize_internal_ids("## A\n\n- x\n- y") == "## A\n\n- x\n- y"
