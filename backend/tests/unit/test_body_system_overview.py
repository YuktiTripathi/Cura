"""Dynamic body-system overview: built only from the results a member's report actually holds."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest

from app.biomarkers import overview as overview_module
from app.biomarkers.overview import ReportNotFound, build_body_system_overview
from app.biomarkers.registry import REGISTRY_CSV, load_registry
from app.biomarkers.resolver import resolve_marker
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import MarkerFlag

DAY = date(2026, 8, 18)


def m(name, value, *, key=None, unit="U/L", low=None, high=None, flag=None, group=None, mid=None):
    key = key or name.lower().replace(" ", "_")
    if flag is None:
        flag = MarkerFlag.unknown
        if value is None:
            flag = MarkerFlag.missing
        elif low is not None and value < low:
            flag = MarkerFlag.low
        elif high is not None and value > high:
            flag = MarkerFlag.high
        elif low is not None or high is not None:
            flag = MarkerFlag.normal
    return BloodMarker(
        id=mid or f"id-{key}-{name}",
        key=key,
        name=name,
        value=value,
        unit=unit,
        reference_low=low,
        reference_high=high,
        flag=flag,
        category=group,
    )


def report(markers, rid="r1", day=DAY):
    return BloodReport(report_id=rid, report_date=day, markers=markers)


def by_system(overview):
    return {system.id: system for system in overview.systems}


def result(overview, name):
    return next(item for item in overview.results if item.original_name == name)


def primary_total(overview):
    owned = sum(s.available_count for s in overview.systems if s.scope == "primary")
    return owned + (overview.allergy.available_count if overview.allergy else 0)


# ---- registry -----------------------------------------------------------------------------


def test_registry_covers_every_csv_row_and_keeps_source_names():
    reg = load_registry()
    with Path(REGISTRY_CSV).open(encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    assert reg.version
    assert sum(len(e.sources) for e in reg.entries.values()) == len(rows)
    for row in rows:
        entry = reg.entries[row["proposed_canonical_id"]]
        assert any(s.group == row["source_group"] and s.test_name == row["source_test_name"] for s in entry.sources)


def test_one_primary_system_per_test_and_cross_references_are_secondary_only():
    for entry in load_registry().entries.values():
        assert entry.primary_system not in entry.secondary_systems


def test_calcium_esr_and_partial_duplicates_stay_distinct():
    reg = load_registry()
    assert {"calcium", "calcium_total"} <= set(reg.entries)
    assert {"esr", "esr_automated"} <= set(reg.entries)
    assert reg.entries["calcium"].primary_system != reg.entries["calcium_total"].primary_system


def test_shared_hormone_has_one_identity_across_male_and_female_groups():
    entry = load_registry().entries["total_testosterone"]
    assert entry.sex_scopes == {"male_panel", "female_panel"}


def test_every_key_bridge_target_exists():
    reg = load_registry()
    assert all(target in reg.entries for target in reg.key_bridge.values())


@pytest.mark.parametrize(
    "name,key,group,canonical",
    [
        ("HDL Cholestrol Direct", "hdl", None, "hdl_cholesterol_direct"),
        ("Platelate Count", "platelets", None, "platelet_count"),
        ("Haemoglobin", "hemoglobin", None, "hemoglobin_hb"),
        ("SGPT (ALT)", "alt", "Liver Profile", "sgpt_alt"),
        ("Vitamin D", "vitamin_d", None, "vitamin_d_total_25_hydroxy"),
        ("RBC", "rbc", "Complete Hemogram", "red_blood_cells"),
        ("RBC", "rbc", "Urine Routine and Microscopy", "urine_rbc"),
        ("Sugar", "glucose", "Urine Routine and Microscopy", "urine_sugar"),
        ("Sugar", "glucose", None, "fasting_sugar"),
        ("UIBC", None, None, "ubic"),
    ],
)
def test_aliases_and_spelling_variants_resolve(name, key, group, canonical):
    assert resolve_marker(name, key, group).canonical_id == canonical


def test_overview_code_never_calls_a_model():
    for path in Path(overview_module.__file__).parent.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "app.llm" not in text and "openai" not in text.lower(), path.name


# ---- runtime scenarios --------------------------------------------------------------------


def comprehensive():
    return report(
        [
            m("Cholesterol Total", 210, unit="mg/dL", high=200, group="Lipid Profile"),
            m("Triglycerides", 120, unit="mg/dL", high=150, group="Lipid Profile"),
            m("HDL Cholestrol Direct", 38, unit="mg/dL", low=40, group="Lipid Profile"),
            m("SGPT (ALT)", 28, high=45, group="Liver Profile"),
            m("SGOT (AST)", 30, high=40, group="Liver Profile"),
            m("Creatinine", 0.9, unit="mg/dL", low=0.7, high=1.3, group="Kidney Function with K"),
            m("Hemoglobin Hb", 14.2, unit="g/dL", low=13, high=17, group="Complete Hemogram"),
            m("HbA1c", 5.4, unit="%", high=5.6, group="Diabetes Profile Pro+"),
            m("Vitamin D Total-25 Hydroxy", 18, unit="ng/mL", low=30, high=100, group="Vitamins C-Suite"),
            m("TSH", 2.1, unit="uIU/mL", low=0.4, high=4.2, group="Thyroid Profile"),
            m("Cortisol", 14, unit="ug/dL", low=6, high=23, group="Hormones C-suite Male"),
            m("hs-CRP", 1.2, unit="mg/L", high=3, group="Inflammatory"),
            m("PSA", 0.8, unit="ng/mL", high=4, group="Cancer Male C-suite"),
        ]
    )


def test_comprehensive_panel_builds_only_observed_systems_with_exact_counts():
    rep = comprehensive()
    ov = build_body_system_overview([rep])
    systems = by_system(ov)
    assert ov.state == "ready" and ov.report.report_id == "r1"
    assert set(systems) == {
        "heart_circulation", "liver_health", "kidney_urinary", "blood_iron", "blood_sugar_metabolism",
        "vitamins_nutrition", "thyroid_health", "hormonal_health", "immunity_inflammation",
        "cancer_related", "sleep_recovery",
    }
    assert "bone_mineral" not in systems  # only a cross reference exists, no primary result
    assert ov.totals.unique_results == len(rep.markers) == primary_total(ov)
    assert systems["heart_circulation"].available_count == 3
    assert systems["heart_circulation"].abnormal_count == 2
    assert ov.totals.abnormal == sum(1 for x in ov.results if x.status in {"low", "high", "critical"})


def test_card_counts_always_equal_the_input_whatever_the_input_is():
    for size in (1, 2, 5, 9):
        markers = comprehensive().markers[:size]
        ov = build_body_system_overview([report(markers)])
        assert ov.totals.unique_results == size == primary_total(ov)
        assert sum(len(s.result_ids) for s in ov.systems if s.scope == "primary") == size


def test_summary_carries_name_counts_breakdown_findings_and_source():
    ov = build_body_system_overview([comprehensive()])
    heart = by_system(ov)["heart_circulation"]
    assert heart.name == "Heart & Circulation"
    assert (heart.status_breakdown.normal, heart.status_breakdown.high, heart.status_breakdown.low) == (1, 1, 1)
    assert {f.label for f in heart.key_findings} == {"Cholesterol Total", "HDL Cholesterol Direct"}
    assert heart.group_coverage[0].source_group == "Lipid Profile"
    assert heart.latest_measured_on == "2026-08-18"


def test_small_panel_shows_one_card_and_marks_the_group_partial():
    ov = build_body_system_overview([report([m("SGPT (ALT)", 60, high=45, group="Liver Profile"), m("SGOT (AST)", 30, high=40, group="Liver Profile")])])
    assert [s.id for s in ov.systems] == ["liver_health"]
    coverage = ov.systems[0].group_coverage[0]
    assert coverage.observed_count == 2 and coverage.partial is True
    assert coverage.registry_count > coverage.observed_count


def test_isolated_test_produces_exactly_one_card():
    ov = build_body_system_overview([report([m("TSH", 6.1, unit="uIU/mL", low=0.4, high=4.2)])])
    assert [s.id for s in ov.systems] == ["thyroid_health"]
    assert ov.systems[0].state == "attention"
    assert ov.allergy is None


def test_no_reports_gives_an_empty_overview_without_cards():
    ov = build_body_system_overview([])
    assert (ov.available, ov.state, ov.systems, ov.results) == (False, "no_report", [], [])


def test_report_with_no_results_is_not_rendered_as_healthy():
    ov = build_body_system_overview([report([])])
    assert ov.state == "no_results" and ov.systems == []


def test_incomplete_data_is_explicit_never_normal():
    ov = build_body_system_overview(
        [
            report(
                [
                    m("TSH", None, unit="uIU/mL", group="Thyroid Profile"),
                    m("T3", 1.1, unit="ng/mL", group="Thyroid Profile"),
                    m("T4", 8.0, unit="ug/dL", low=5, high=12, group="Thyroid Profile"),
                ]
            )
        ]
    )
    thyroid = by_system(ov)["thyroid_health"]
    assert thyroid.status_breakdown.no_value == 1
    assert thyroid.status_breakdown.no_range == 1
    assert thyroid.status_breakdown.normal == 1
    assert thyroid.state == "partly_assessed"
    assert result(ov, "TSH").status == "no_value"
    assert result(ov, "T3").status == "no_range"


def test_all_values_missing_state():
    ov = build_body_system_overview([report([m("TSH", None, group="Thyroid Profile")])])
    assert ov.systems[0].state == "no_values" and ov.systems[0].abnormal_count == 0


def test_exact_duplicates_collapse_and_do_not_inflate_counts():
    rep = report(
        [
            m("SGPT (ALT)", 60, high=45, group="Liver Profile", mid="a"),
            m("SGPT (ALT)", 60, high=45, group="Liver Profile", mid="b"),
            m("SGOT (AST)", 30, high=40, group="Liver Profile"),
        ]
    )
    ov = build_body_system_overview([rep])
    assert ov.totals.unique_results == 2
    assert ov.totals.duplicates_collapsed == 1
    assert by_system(ov)["liver_health"].available_count == 2
    assert result(ov, "SGPT (ALT)").duplicates_collapsed == 1


def test_conflicting_duplicate_keeps_one_value_and_lists_the_other():
    rep = report([m("Creatinine", 0.9, unit="mg/dL", low=0.7, high=1.3, mid="a"), m("Creatinine", 1.8, unit="mg/dL", low=0.7, high=1.3, mid="b")])
    ov = build_body_system_overview([rep])
    assert ov.totals.unique_results == 1 and ov.totals.conflicting_duplicates == 1
    item = result(ov, "Creatinine")
    assert item.value == 0.9 and item.conflicting_values == [1.8]


def test_same_test_in_a_different_unit_is_not_merged():
    rep = report([m("Creatinine", 0.9, unit="mg/dL", mid="a"), m("Creatinine", 80, unit="umol/L", mid="b")])
    assert build_body_system_overview([rep]).totals.unique_results == 2


def test_overlapping_systems_are_cross_listed_without_inflating_totals():
    rep = report(
        [
            m("Vitamin D Total-25 Hydroxy", 18, unit="ng/mL", low=30, high=100, group="Vitamins C-Suite"),
            m("Magnesium", 1.4, unit="mg/dL", low=1.7, high=2.2, group="Sleep"),
            m("Calcium Total", 9.1, unit="mg/dL", low=8.6, high=10.2, group="Kidney Function with K"),
        ]
    )
    ov = build_body_system_overview([rep])
    systems = by_system(ov)
    assert ov.totals.unique_results == 3 == primary_total(ov)
    assert len(systems["vitamins_nutrition"].result_ids) == 2  # vitamin D and magnesium are primary here
    assert "bone_mineral" not in systems  # no primary bone result, so no bone card
    sleep = systems["sleep_recovery"]
    assert sleep.scope == "related_only" and sleep.result_ids == []
    assert len(sleep.related_result_ids) == 1 and sleep.available_count == 1
    assert sleep.caveat and "do not measure how well you sleep" in sleep.caveat
    # Report-wide totals never count the sleep card again.
    assert sum(s.available_count for s in ov.systems if s.scope == "primary") == 3


def test_cross_reference_shows_in_a_system_that_has_its_own_results():
    rep = report(
        [
            m("Calcium", 9.4, unit="mg/dL", low=8.6, high=10.2, group="Bone health"),
            m("Vitamin D Total-25 Hydroxy", 18, unit="ng/mL", low=30, high=100, group="Vitamins C-Suite"),
        ]
    )
    ov = build_body_system_overview([rep])
    bone = by_system(ov)["bone_mineral"]
    assert len(bone.result_ids) == 1 and len(bone.related_result_ids) == 1
    assert bone.related_abnormal_count == 1 and bone.abnormal_count == 0
    assert ov.totals.unique_results == 2


def test_sleep_recovery_is_absent_without_related_results():
    ov = build_body_system_overview([report([m("TSH", 2, low=0.4, high=4.2)])])
    assert "sleep_recovery" not in by_system(ov)


def test_male_and_female_specific_results_display_whatever_the_panel():
    male = build_body_system_overview([report([m("PSA", 5.2, unit="ng/mL", high=4, group="Cancer Male C-suite"), m("Total Testosterone", 600, unit="ng/dL", group="Hormones C-suite Male")])])
    female = build_body_system_overview([report([m("CA 125", 12, unit="U/mL", high=35, group="Cancer Female C-suite"), m("LH", 5, unit="mIU/mL", group="Hormones C-suite Female"), m("Total Testosterone", 40, unit="ng/dL", group="Hormones C-suite Female")])])
    assert set(by_system(male)) == {"cancer_related", "hormonal_health"}
    assert set(by_system(female)) == {"cancer_related", "hormonal_health"}
    assert by_system(male)["cancer_related"].caveat and "not a cancer screening" in by_system(male)["cancer_related"].caveat
    assert result(male, "Total Testosterone").canonical_id == result(female, "Total Testosterone").canonical_id
    # A panel group never decides eligibility: a female group result appears for any member who has it.
    assert by_system(male)["cancer_related"].available_count == 1


def test_unknown_names_are_kept_under_other_results_for_review():
    rep = report([m("Zorbitol Index", 3.3, key="zorbitol_index", unit="u", low=1, high=2), m("TSH", 2, low=0.4, high=4.2)])
    ov = build_body_system_overview([rep])
    other = by_system(ov)["other_unmapped"]
    assert other.needs_mapping_review and other.available_count == 1
    item = result(ov, "Zorbitol Index")
    assert item.canonical_id is None and item.needs_mapping_review and item.value == 3.3
    assert item.status == "high"  # the lab's own range still applies
    assert ov.totals.unmapped == 1 and ov.totals.unique_results == 2
    assert [s.id for s in ov.systems][-1] == "other_unmapped"


def test_tests_outside_the_supplied_registry_are_not_guessed_into_a_system():
    ferritin = build_body_system_overview([report([m("Ferritin", 5, key="ferritin")])])
    assert [s.id for s in ferritin.systems] == ["blood_iron"]
    unknown = build_body_system_overview([report([m("Not A Real Assay", 5, key="not_a_real_assay")])])
    assert [s.id for s in unknown.systems] == ["other_unmapped"]


def test_report_flags_values_units_ranges_and_dates_are_preserved():
    marker = m("Triglycerides", 160, unit="mg/dL", low=0, high=150, flag=MarkerFlag.critical, group="Lipid Profile")
    marker.measured_at = date(2026, 8, 10)
    ov = build_body_system_overview([report([marker])])
    item = ov.results[0]
    assert (item.value, item.unit, item.reference_low, item.reference_high) == (160, "mg/dL", 0, 150)
    assert item.status == "critical" and item.status_source == "report_flag" and item.report_flag == "critical"
    assert item.measured_on == "2026-08-10" and item.original_name == "Triglycerides"


def test_the_reports_normal_flag_is_not_second_guessed():
    ov = build_body_system_overview([report([m("Triglycerides", 160, unit="mg/dL", high=150, flag=MarkerFlag.normal)])])
    assert ov.results[0].status == "normal"


def test_missing_flag_falls_back_to_the_labs_own_range_and_says_so():
    bare = BloodMarker(id="x", key="triglycerides", name="Triglycerides", value=160, unit="mg/dL", reference_high=150, flag=MarkerFlag.unknown)
    item = build_body_system_overview([report([bare])]).results[0]
    assert item.status == "high" and item.status_source == "reference_range"


def test_spelling_slips_are_repaired_for_display_only():
    ov = build_body_system_overview([report([m("HDL Cholestrol Direct", 50, unit="mg/dL", low=40)])])
    item = ov.results[0]
    assert item.display_name == "HDL Cholesterol Direct" and item.original_name == "HDL Cholestrol Direct"


def test_derived_indices_are_listed_but_never_a_key_finding():
    rep = report([m("MENTZER INDEX MCV/RCC", 20, unit="", low=0, high=13, group="Complete Hemogram"), m("Hemoglobin Hb", 9, unit="g/dL", low=13, high=17, group="Complete Hemogram")])
    ov = build_body_system_overview([rep])
    item = result(ov, "MENTZER INDEX MCV/RCC")
    assert item.is_derived and item.note and "never recomputed" in item.note
    blood = by_system(ov)["blood_iron"]
    assert [f.label for f in blood.key_findings] == ["Hemoglobin Hb"]
    assert blood.abnormal_count == 2


def test_allergy_results_form_a_separate_section_not_a_body_system():
    rep = report([m("Cow Milk", 0.9, unit="kU/L", high=0.35, group="Allergy Dairy"), m("TSH", 2, low=0.4, high=4.2)])
    ov = build_body_system_overview([rep])
    assert ov.allergy and ov.allergy.id == "allergy" and ov.allergy.available_count == 1
    assert ov.allergy.subsections[0].name == "Food"
    assert "allergy" not in by_system(ov) and ov.totals.allergy == 1 and ov.totals.unique_results == 2
    assert "not a diagnosis" in ov.allergy.caveat


def test_no_allergy_section_without_allergy_results():
    assert build_body_system_overview([comprehensive()]).allergy is None


def test_historical_report_can_be_selected_and_trends_only_use_earlier_reports():
    old = report([m("LDL Cholestrol Calculated", 150, key="ldl", unit="mg/dL", high=100, group="Lipid Profile")], rid="old", day=date(2026, 1, 5))
    new = report([m("LDL Cholestrol Calculated", 130, key="ldl", unit="mg/dL", high=100, group="Lipid Profile")], rid="new", day=date(2026, 8, 18))
    latest = build_body_system_overview([new, old])
    assert latest.report.report_id == "new"
    assert [r.report_id for r in latest.available_reports] == ["new", "old"]
    item = latest.results[0]
    assert item.previous_value == 150 and item.trend == "toward_range" and item.change == "decreased"
    assert [p.value for p in item.history] == [150, 130]
    earlier = build_body_system_overview([new, old], report_id="old")
    assert earlier.results[0].history == [] and earlier.results[0].previous_value is None


def test_trend_never_mixes_units():
    old = report([m("Creatinine", 80, unit="umol/L")], rid="old", day=date(2026, 1, 5))
    new = report([m("Creatinine", 0.9, unit="mg/dL")], rid="new")
    item = build_body_system_overview([old, new]).results[0]
    assert item.previous_value is None and item.history == []
    assert item.history_note and "different unit" in item.history_note


def test_unknown_report_id_raises():
    with pytest.raises(ReportNotFound):
        build_body_system_overview([comprehensive()], report_id="nope")


def test_result_ids_are_unique_and_every_card_id_resolves():
    ov = build_body_system_overview([comprehensive()])
    ids = [r.result_id for r in ov.results]
    assert len(ids) == len(set(ids))
    for system in ov.systems:
        assert set(system.result_ids + system.related_result_ids) <= set(ids)


def test_systems_needing_attention_are_listed_first_without_changing_the_set():
    ov = build_body_system_overview([comprehensive()])
    primaries = [s for s in ov.systems if s.scope == "primary"]
    flags = [s.abnormal_count > 0 for s in primaries]
    assert flags == sorted(flags, reverse=True)
    assert ov.systems[-1].scope == "related_only"


def test_every_card_says_in_plain_words_what_the_system_covers():
    ov = build_body_system_overview([comprehensive()])
    assert all(system.about for system in ov.systems)
    assert "dash" not in "".join(system.about for system in ov.systems)
