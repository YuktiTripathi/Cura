"""Canonical mapping for the 2.3 library.

A workbook key is never a production biomarker id. An alias or label match
stays unconfirmed. Only an exact id already in the CURA registry is confirmed.
"""

from __future__ import annotations

from app.biomarkers.medical_registry import inventory
from app.biomarkers.registry import load_registry


def mapping_rows() -> list[dict]:
    registry = load_registry()
    rows = []
    for item in inventory():
        content_key = item.get("inventory_id") or ""
        proposed = item.get("biomarker_id") or ""
        status = item.get("mapping_status") or "unresolved"
        exact = bool(proposed) and proposed in registry.entries and not content_key.startswith("WB-")
        # Workbook keys are local references even when the proposed id matches.
        confirmed = exact and status == "matched_registry_label_or_alias" and not str(proposed).startswith("WB-")
        # The proposed id may match, but the library's own status is still a label match.
        # Do not promote that to approved. Record the exact-id evidence separately.
        rows.append(
            {
                "original_test_name": item.get("original_test_name"),
                "content_key": content_key,
                "provider_identifier": proposed if status != "unresolved" else "",
                "canonical_identifier": proposed if proposed in registry.entries else "",
                "mapping_evidence": (
                    "exact_registry_id"
                    if proposed in registry.entries
                    else "unresolved_no_exact_registry_id"
                ),
                "library_mapping_status": status,
                "approval_status": "unconfirmed",
                "review_status": item.get("review_status"),
                "promoted": False,
                "exact_id_in_registry": proposed in registry.entries,
                "confirmed_for_production": confirmed and item.get("review_status") == "human_clinically_approved",
            }
        )
    return rows
