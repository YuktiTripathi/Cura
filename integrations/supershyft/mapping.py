"""Map SuperShyft `individual_health_report` JSON into Cura DTOs. Read-only."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any

from app.contracts.bio_ai import BioAIReport, BioAIRisk
from app.contracts.blood import BloodMarker, BloodReport
from app.contracts.common import MarkerFlag
from app.pipeline.lab_parameters import canonicalize_marker_name, is_lab_key

_SKIP_SUFFIXES = ("_unit", "_range", "_flag", "_status", "_ref")


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return date.today()


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag(
    value: float | None,
    low: float | None,
    high: float | None,
    supplied: Any = None,
) -> MarkerFlag:
    normalized = str(supplied or "").strip().lower()
    if normalized in {flag.value for flag in MarkerFlag}:
        return MarkerFlag(normalized)
    if value is None:
        return MarkerFlag.missing
    if low is not None and value < low:
        return MarkerFlag.low
    if high is not None and value > high:
        return MarkerFlag.high
    if low is None and high is None:
        return MarkerFlag.unknown
    return MarkerFlag.normal


def _skip_derived_lab_name(name: str) -> bool:
    """Skip ratios and calculated-from-lipid extras that alias onto LDL/HDL keys."""
    raw = name or ""
    lowered = re.sub(r"[\s_]+", " ", raw.lower())
    if "ratio" in lowered:
        return True
    if "non-hdl" in lowered or "non hdl" in lowered:
        return True
    if "/" in raw and any(token in lowered for token in ("ldl", "hdl", "chol")):
        return True
    return False


def _key(name: str) -> str:
    lab = canonicalize_marker_name(name)
    if is_lab_key(lab):
        return lab
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    slug = slug.replace("cholestrol", "cholesterol")
    aliases = {
        "haemoglobin": "hemoglobin",
        "hemoglobin_hb": "hemoglobin",
        "hba1c": "hba1c",
        "hba1c_glycosylated_hemoglobin": "hba1c",
        "ldl_cholesterol": "ldl",
        "ldl_cholesterol_calculated": "ldl",
        "hdl_cholesterol": "hdl",
        "hdl_cholesterol_direct": "hdl",
        "serum_hdl_cholesterol": "hdl",
        "vitamin_d": "vitamin_d",
        "vitamin_b12": "vitamin_b12",
        "fasting_blood_sugar": "fasting_blood_glucose",
        "fasting_blood_glucose": "fasting_blood_glucose",
        "fasting_glucose": "fasting_blood_glucose",
        "fbs": "fasting_blood_glucose",
        "blood_sugar": "glucose",
        "glucose": "glucose",
        "total_cholesterol": "cholesterol",
        "cholesterol_total": "cholesterol",
        "cholesterol": "cholesterol",
        "serum_triglycerides": "triglycerides",
        "triglycerides": "triglycerides",
        "uric_acid": "uric_acid",
        "diabetes": "type_2_diabetes",
        "type_2_diabetes": "type_2_diabetes",
        "thyroid_health": "thyroid",
        "pcod": "pcos",
        "pcos": "pcos",
        "polycystic_ovarian_disease": "pcos",
        "polycystic_ovary_syndrome": "pcos",
    }
    return aliases.get(slug, slug or "marker")


def markers_from_blood_parameters(blob: Any) -> list[BloodMarker]:
    if blob is None:
        return []
    if isinstance(blob, list):
        return _from_grouped(blob)
    if isinstance(blob, dict) and isinstance(blob.get("parameters"), dict):
        return _from_canonical(blob["parameters"])
    if isinstance(blob, dict):
        return _from_flat(blob)
    return []


def _from_grouped(groups: list[Any]) -> list[BloodMarker]:
    out: list[BloodMarker] = []
    for i, group in enumerate(groups):
        if not isinstance(group, dict):
            continue
        category = group.get("group_name")
        tests = group.get("tests") or []
        if not isinstance(tests, list):
            continue
        for j, test in enumerate(tests):
            if not isinstance(test, dict):
                continue
            name = str(test.get("test_name") or test.get("parameter_key") or "marker")
            if _skip_derived_lab_name(name) or _skip_derived_lab_name(str(test.get("parameter_key") or "")):
                continue
            key = _key(str(test.get("parameter_key") or name))
            value = _float(test.get("value"))
            if value is None:
                value = _float(test.get("machine_value"))
            low = _float(test.get("lower_range"))
            high = _float(test.get("higher_range"))
            out.append(
                BloodMarker(
                    id=f"{key}-{i}-{j}",
                    key=key,
                    name=name,
                    value=value,
                    unit=test.get("unit"),
                    reference_low=low,
                    reference_high=high,
                    flag=_flag(value, low, high, test.get("flag") or test.get("status")),
                    category=category,
                )
            )
    return out


def _from_canonical(params: dict[str, Any]) -> list[BloodMarker]:
    out: list[BloodMarker] = []
    for key, payload in params.items():
        if not isinstance(payload, dict):
            continue
        value = _float(payload.get("value"))
        low = _float(payload.get("lower_range"))
        high = _float(payload.get("higher_range"))
        name = str(payload.get("provider_test_name") or key)
        out.append(
            BloodMarker(
                id=key,
                key=_key(key),
                name=name,
                value=value,
                unit=payload.get("unit"),
                reference_low=low,
                reference_high=high,
                flag=_flag(value, low, high, payload.get("flag") or payload.get("status")),
            )
        )
    return out


def _from_flat(blob: dict[str, Any]) -> list[BloodMarker]:
    out: list[BloodMarker] = []
    for key, raw in blob.items():
        if not isinstance(key, str):
            continue
        if key in {"id", "is_complete", "created_at", "updated_at"}:
            continue
        if key.endswith(_SKIP_SUFFIXES):
            continue
        value = _float(raw)
        unit = blob.get(f"{key}_unit")
        low = high = None
        rng = blob.get(f"{key}_range")
        if isinstance(rng, str) and "-" in rng:
            parts = rng.replace("–", "-").split("-", 1)
            low, high = _float(parts[0]), _float(parts[1])
        out.append(
            BloodMarker(
                id=key,
                key=_key(key),
                name=key.replace("_", " ").title(),
                value=value,
                unit=str(unit) if unit else None,
                reference_low=low,
                reference_high=high,
                flag=_flag(value, low, high, blob.get(f"{key}_flag") or blob.get(f"{key}_status")),
            )
        )
    return out


def markers_from_digital_data(blob: Any) -> list[BloodMarker]:
    """Map SuperShyft blood_report_raw.digital_data items. Values stay source-exact."""
    if not isinstance(blob, dict):
        return []
    items = blob.get("digital_data")
    if not isinstance(items, list):
        return []
    out: list[BloodMarker] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = str(item.get("test_name") or item.get("parameter_key") or item.get("name") or "")
        if not name:
            continue
        if _skip_derived_lab_name(name) or _skip_derived_lab_name(str(item.get("parameter_key") or "")):
            continue
        if str(item.get("unit") or "").strip().lower() == "ratio":
            continue
        key = _key(name)
        if "ratio" in key:
            continue
        value = _float(item.get("value"))
        if value is None:
            value = _float(item.get("machine_value"))
        low = _float(item.get("min_range") or item.get("lower_range"))
        high = _float(item.get("max_range") or item.get("higher_range"))
        out.append(
            BloodMarker(
                id=f"raw-{key}-{i}",
                key=key,
                name=name,
                value=value,
                unit=item.get("unit"),
                reference_low=low,
                reference_high=high,
                flag=_flag(value, low, high, item.get("flag") or item.get("status")),
            )
        )
    for field, key, label, unit in (
        ("systolic_value", "systolic", "Systolic pressure", "mmHg"),
        ("diastolic_value", "diastolic", "Diastolic pressure", "mmHg"),
    ):
        value = _float(blob.get(field))
        if value is None:
            continue
        out.append(
            BloodMarker(
                id=f"raw-{key}",
                key=key,
                name=label,
                value=value,
                unit=unit,
                flag=_flag(value, None, None),
            )
        )
    return out


def _merge_markers(primary: list[BloodMarker], extra: list[BloodMarker]) -> list[BloodMarker]:
    by_key: dict[str, BloodMarker] = {}
    for marker in primary:
        current = by_key.get(marker.key)
        if current is None or (current.value is None and marker.value is not None):
            by_key[marker.key] = marker
    for marker in extra:
        current = by_key.get(marker.key)
        if current is None:
            by_key[marker.key] = marker
        elif current.value is None and marker.value is not None:
            by_key[marker.key] = marker
    return list(by_key.values())


def _coerce_reports(blob: Any) -> dict[str, Any]:
    if isinstance(blob, str) and blob.strip():
        try:
            blob = json.loads(blob)
        except (TypeError, ValueError):
            return {}
    if not isinstance(blob, dict):
        return {}
    return blob


def _unwrap_reports(blob: Any) -> dict[str, Any]:
    reports = _coerce_reports(blob)
    if not reports:
        return {}
    data = reports.get("data")
    if isinstance(data, dict) and (
        "diseases" in data or "metabolic_age" in data or "blood_parameters" in data
    ):
        return data
    return reports


def _optional_id(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _row_provenance(row: Any) -> dict[str, str | None]:
    return {
        "assessment_instance_id": _optional_id(getattr(row, "assessment_instance_id", None)),
        "engagement_id": _optional_id(getattr(row, "engagement_id", None)),
        "report_url": _optional_id(getattr(row, "report_url", None)),
    }


def _parse_completed_at(value: Any) -> date | datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if "T" in text or len(text) > 10:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _row_completed_at(row: Any) -> date | datetime | None:
    parsed = _parse_completed_at(getattr(row, "created_at", None))
    if parsed is not None:
        return parsed
    reports = _unwrap_reports(getattr(row, "reports", None))
    return _parse_completed_at(reports.get("created_at"))


def _row_report_date(row: Any) -> date:
    completed = _row_completed_at(row)
    if isinstance(completed, datetime):
        return completed.date()
    if isinstance(completed, date):
        return completed
    return date.today()


def markers_from_reports(blob: Any) -> list[BloodMarker]:
    """Parse blood biomarkers from the live `reports` JSON only. No invented columns."""
    reports = _unwrap_reports(blob)
    if not reports:
        return []
    markers: list[BloodMarker] = []
    markers = _merge_markers(markers, markers_from_blood_parameters(reports.get("blood_parameters")))
    raw = reports.get("blood_report_raw")
    if isinstance(raw, dict):
        markers = _merge_markers(markers, markers_from_digital_data(raw))
    elif isinstance(reports.get("digital_data"), list):
        markers = _merge_markers(markers, markers_from_digital_data(reports))
    record = reports.get("record")
    if isinstance(record, str) and record.strip().startswith(("{", "[")):
        try:
            record = json.loads(record)
        except (TypeError, ValueError):
            record = None
    if isinstance(record, dict):
        nested = record.get("blood_parameters")
        markers = _merge_markers(
            markers,
            markers_from_blood_parameters(nested if nested is not None else record),
        )
        raw_record = record.get("blood_report_raw") if isinstance(record.get("blood_report_raw"), dict) else record
        if isinstance(record.get("digital_data"), list) or isinstance(record.get("blood_report_raw"), dict):
            markers = _merge_markers(markers, markers_from_digital_data(raw_record))
    return markers


def blood_report_from_row(row: Any) -> BloodReport | None:
    markers = markers_from_reports(getattr(row, "reports", None))
    if not markers:
        return None
    report_id = str(row.report_id)
    measured_at = _row_report_date(row)
    markers = [
        marker.model_copy(
            update={
                "source": "supershyft",
                "report_id": report_id,
                "measured_at": measured_at,
            }
        )
        for marker in markers
    ]
    return BloodReport(
        report_id=report_id,
        report_date=measured_at,
        source="blood_report",
        markers=markers,
        **_row_provenance(row),
    )


def _row_attr(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def markers_from_booking_payload(blood_parameters: Any, blood_report_raw: Any) -> list[BloodMarker]:
    """Map participant_blood_bookings JSON. Prefer digital_data values over empty parameters."""
    markers: list[BloodMarker] = []
    markers = _merge_markers(markers, markers_from_blood_parameters(blood_parameters))
    raw = blood_report_raw
    if isinstance(raw, str) and raw.strip():
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            raw = None
    if isinstance(raw, dict):
        markers = _merge_markers(markers, markers_from_digital_data(raw))
    return markers


def _booking_report_date(row: Any) -> date:
    for key in ("collection_date", "collected_at", "created_at"):
        parsed = _parse_completed_at(_row_attr(row, key))
        if isinstance(parsed, datetime):
            return parsed.date()
        if isinstance(parsed, date):
            return parsed
    return date.today()


def blood_report_from_booking_row(row: Any) -> BloodReport | None:
    markers = markers_from_booking_payload(
        _row_attr(row, "blood_parameters"),
        _row_attr(row, "blood_report_raw"),
    )
    if not markers:
        return None
    booking_id = _row_attr(row, "id")
    if booking_id is None or booking_id == "":
        return None
    report_id = f"blood-{booking_id}"
    measured_at = _booking_report_date(row)
    markers = [
        marker.model_copy(
            update={
                "source": "supershyft",
                "report_id": report_id,
                "measured_at": measured_at,
            }
        )
        for marker in markers
    ]
    return BloodReport(
        report_id=report_id,
        report_date=measured_at,
        source="blood_report",
        markers=markers,
        assessment_instance_id=_optional_id(_row_attr(row, "assessment_instance_id")),
        engagement_id=_optional_id(_row_attr(row, "engagement_id")),
        report_url=_optional_id(_row_attr(row, "diagnostic_report_url")),
    )


def bio_ai_from_row(row: Any) -> BioAIReport | None:
    reports = _unwrap_reports(getattr(row, "reports", None))
    if not reports:
        return None
    diseases = reports.get("diseases")
    if not isinstance(diseases, list):
        diseases = []
    risks: list[BioAIRisk] = []
    provenance = _row_provenance(row)
    measured_at = _row_completed_at(row) or _row_report_date(row)
    for item in diseases:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code") or item.get("id") or item.get("name") or "").strip()
        if not code:
            continue
        name = str(item.get("name") or item.get("display_name") or code)
        score = _float(item.get("risk_score_scaled") or item.get("score") or item.get("risk_score"))
        risks.append(
            BioAIRisk(
                code=_key(code),
                name=name,
                score=score,
                status=str(item.get("status") or item.get("risk_status") or item.get("band") or "") or None,
                percentile=_float(item.get("percentile") or item.get("disease_percentile")),
                lifestyle_contribution=_float(item.get("lifestyle_contribution")),
                contributing_factors=[
                    str(value)
                    for value in (item.get("contributing_factors") or item.get("factors") or [])
                    if value
                ],
                report_id=f"bioai-{row.report_id}",
                measured_at=measured_at,
                assessment_instance_id=provenance.get("assessment_instance_id"),
            )
        )
    metabolic_age = _float(reports.get("metabolic_age"))
    metabolic_score = _float(reports.get("metabolic_score"))
    if metabolic_age is None and metabolic_score is None and not risks:
        return None
    source = "advanced_bio_ai" if reports.get("advanced") else "bio_ai"
    report_date = _row_report_date(row)
    return BioAIReport(
        report_id=f"bioai-{row.report_id}",
        report_date=report_date,
        source_line=source,  # type: ignore[arg-type]
        metabolic_age=metabolic_age,
        metabolic_score=metabolic_score,
        risks=risks,
        **_row_provenance(row),
    )
