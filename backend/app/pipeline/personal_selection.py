"""Select personal measurements from already-authorized reports.

This module never chooses a user_id. Callers must pass reports already scoped
to the authenticated principal.
"""

from __future__ import annotations

from app.contracts.bio_ai import BioAIReport, BioAIRisk
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.query import QueryPlan
from app.pipeline.lab_parameters import (
    DERIVED_ENTITY_KEYS,
    FAMILY_QUERY_KEYS,
    canonicalize_marker_name,
    display_name_for,
    expand_requested_keys,
    is_lab_key,
)


def wanted_metric_keys(plan: QueryPlan) -> list[str]:
    keys = list(plan.requested_metrics or [])
    if not keys and plan.topic and (is_lab_key(plan.topic) or plan.topic in FAMILY_QUERY_KEYS):
        keys = [plan.topic]
    skip = {item.lower() for item in (plan.reasoning_context or [])} | {
        item.lower() for item in (plan.optional_entities or [])
    }
    return [
        key
        for key in expand_requested_keys(keys)
        if key not in DERIVED_ENTITY_KEYS
        and (is_lab_key(key) or key in FAMILY_QUERY_KEYS)
        and key.lower() not in skip
    ]


def retain_blood_reports(reports: list[BloodReport], wanted: set[str]) -> list[BloodReport]:
    """Keep report identity when requested markers are absent. Do not drop the report."""
    out: list[BloodReport] = []
    for report in reports:
        markers = [item for item in report.markers if item.key in wanted]
        out.append(report.model_copy(update={"markers": markers}))
    return out


def _ordered_reports(reports: list[BloodReport]) -> list[BloodReport]:
    return sorted(reports, key=lambda report: (report.report_date, report.report_id))


def _ordered_bio_reports(reports: list[BioAIReport]) -> list[BioAIReport]:
    return sorted(reports, key=lambda report: (report.report_date, report.report_id))


def _usable_marker(marker: BloodMarker) -> bool:
    return marker.value is not None


def _marker_matches(marker: BloodMarker, key: str, reports: list[BloodReport]) -> bool:
    """Alias match without copying a value from a chemically different test.

    BUN and urea share a family, but if both are stored they stay separate.
    A BUN-only report still answers a BUN / blood-urea-nitrogen question.
    """
    if marker.key == key:
        return True
    wanted = canonicalize_marker_name(key)
    stored = canonicalize_marker_name(marker.key) or canonicalize_marker_name(marker.name or "")
    if wanted == stored:
        return True
    bun_family = {"bun", "urea"}
    if wanted in bun_family and stored in bun_family and wanted != stored:
        keys_present = {canonicalize_marker_name(item.key) for report in reports for item in report.markers}
        return stored in keys_present and wanted not in keys_present
    return False


def select_latest_markers(
    reports: list[BloodReport],
    keys: list[str],
) -> tuple[list[BloodMarker], list[str]]:
    selected: list[BloodMarker] = []
    missing: list[str] = []
    ordered = _ordered_reports(reports)
    for key in keys:
        found = None
        for report in reversed(ordered):
            marker = next(
                (item for item in report.markers if _marker_matches(item, key, reports) and _usable_marker(item)),
                None,
            )
            if marker is None:
                continue
            found = marker.model_copy(
                update={
                    "report_id": marker.report_id or report.report_id,
                    "measured_at": marker.measured_at or report.report_date,
                }
            )
            break
        if found:
            selected.append(found)
        else:
            missing.append(key)
    return selected, missing


def select_previous_markers(
    reports: list[BloodReport],
    keys: list[str],
) -> tuple[list[BloodMarker], list[str]]:
    selected: list[BloodMarker] = []
    missing: list[str] = []
    ordered = _ordered_reports(reports)
    for key in keys:
        hits: list[BloodMarker] = []
        for report in ordered:
            marker = next(
                (item for item in report.markers if _marker_matches(item, key, reports) and _usable_marker(item)),
                None,
            )
            if marker is None:
                continue
            hits.append(
                marker.model_copy(
                    update={
                        "report_id": marker.report_id or report.report_id,
                        "measured_at": marker.measured_at or report.report_date,
                    }
                )
            )
        if len(hits) >= 2:
            selected.append(hits[-2])
        else:
            missing.append(key)
    return selected, missing


def measurements_for_key(reports: list[BloodReport], key: str) -> list[tuple[BloodReport, BloodMarker]]:
    out: list[tuple[BloodReport, BloodMarker]] = []
    for report in _ordered_reports(reports):
        marker = next(
            (item for item in report.markers if item.key == key and _usable_marker(item)),
            None,
        )
        if marker is not None:
            out.append((report, marker))
    return out


def latest_report(reports: list[BloodReport]) -> BloodReport | None:
    ordered = _ordered_reports(reports)
    return ordered[-1] if ordered else None


def latest_bio_report(reports: list[BioAIReport]) -> BioAIReport | None:
    ordered = _ordered_bio_reports(reports)
    return ordered[-1] if ordered else None


def previous_bio_report(reports: list[BioAIReport]) -> BioAIReport | None:
    ordered = _ordered_bio_reports(reports)
    return ordered[-2] if len(ordered) >= 2 else None


BIO_CODE_VARIANTS = {
    "pcos": ("pcos", "pcod", "polycystic_ovarian_disease", "polycystic_ovary_syndrome", "polycystic"),
    "type_2_diabetes": ("type_2_diabetes", "diabetes", "t2dm"),
    "cardiac_health": ("cardiac_health", "cardiac", "heart"),
    "nafld": ("nafld", "fatty_liver"),
}


def _bio_code_options(code: str) -> set[str]:
    slug = (code or "").strip().lower().replace("-", "_")
    options = {slug}
    for canonical, variants in BIO_CODE_VARIANTS.items():
        if slug == canonical or slug in variants:
            options.add(canonical)
            options.update(variants)
    return options


def select_bio_risks(report: BioAIReport, codes: list[str]) -> tuple[list[BioAIRisk], list[str]]:
    if not codes:
        return list(report.risks), []
    selected: list[BioAIRisk] = []
    missing: list[str] = []
    for code in codes:
        options = _bio_code_options(code)
        risk = next((item for item in report.risks if (item.code or "").lower() in options), None)
        if risk is None:
            missing.append(code)
            continue
        selected.append(risk)
    return selected, missing


def display_missing(key: str) -> str:
    return display_name_for(key)
