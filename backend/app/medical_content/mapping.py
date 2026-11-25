"""Exact canonical matches only. Ambiguous workbook labels stay unresolved."""

from __future__ import annotations

from app.biomarkers.registry import load_registry as load_biomarker_registry
from app.medical_content.registry import load_registry


def mapping_rows() -> list[dict]:
    content = load_registry()
    clinical = load_biomarker_registry()
    known = set(clinical.entries)
    bridged = set(clinical.key_bridge.values())
    rows = []
    for entry in content["biomarkers"]:
        marker_id = (entry.get("biomarker_id") or "").strip()
        content_key = entry.get("content_key") or ""
        resolved = None
        if marker_id and (marker_id in known or marker_id in bridged):
            resolved = marker_id
            evidence_text = "biomarker_id equals a canonical id or key-bridge target"
        else:
            from app.biomarkers.resolver import resolve_marker

            label = (entry.get("clinical_name") or "")
            hit = resolve_marker(label, marker_id or None)
            if hit.canonical_id and hit.method in {"source_label", "source_group_label", "alias", "slug", "cura_key"}:
                resolved = hit.canonical_id
                evidence_text = f"exact resolver method {hit.method}"
        if resolved:
            status = "exact_canonical_match"
            canonical = resolved
            evidence = evidence_text
        else:
            status = "unresolved"
            canonical = None
            evidence = "no exact canonical id; workbook label was not fuzzy-matched"
        rows.append({
            "original_test_name": (entry.get("original_test_names") or [entry.get("clinical_name")])[0],
            "content_key": content_key,
            "provider_identifier": None,
            "canonical_identifier": canonical,
            "mapping_evidence": evidence,
            "approval_status": entry.get("review_status") or "pending_clinical_review",
            "mapping_status": status,
        })
    for item in content["unresolved"]:
        if any(row["content_key"] == item.get("inventory_id") for row in rows):
            continue
        rows.append({
            "original_test_name": item.get("original_test_name"),
            "content_key": item.get("inventory_id"),
            "provider_identifier": None,
            "canonical_identifier": None,
            "mapping_evidence": item.get("reason"),
            "approval_status": item.get("approval_status") or "requires_phase_2b_approval",
            "mapping_status": "unresolved",
        })
    return rows


def confirmed_ids() -> set[str]:
    return {row["canonical_identifier"] for row in mapping_rows() if row["mapping_status"] == "exact_canonical_match"}
