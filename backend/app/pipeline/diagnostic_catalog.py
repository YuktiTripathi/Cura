"""Load the SuperShyft diagnostic catalog (live DB or mock seed names)."""

from __future__ import annotations

import json
from functools import lru_cache

from app.contracts.diagnostics import CatalogItemKind, DiagnosticCatalogItem
from app.core.config import settings
from app.pipeline.lab_parameters import display_name_for
from integrations.mock.loader import DATA_DIR

_MOCK_PATH = DATA_DIR / "diagnostic_catalog.json"


def _from_record(row: dict, *, kind: CatalogItemKind) -> DiagnosticCatalogItem:
    included = [str(item) for item in (row.get("included_tests") or []) if item]
    labels = {key: display_name_for(key) for key in included}
    status = str(row.get("status") or "active").strip().lower() or "active"
    return DiagnosticCatalogItem(
        catalog_id=str(row.get("catalog_id")),
        kind=kind,
        display_name=str(row.get("display_name") or row.get("catalog_id")),
        provider=row.get("provider") or "SuperShyft",
        included_tests=included,
        included_test_labels=labels,
        price=float(row["price"]) if row.get("price") is not None else None,
        currency=str(row.get("currency") or "INR"),
        status=status,
        gender_suitability=row.get("gender_suitability"),
        collection_type=row.get("collection_type"),
        extra_test_count=len(included),
    )


@lru_cache(maxsize=1)
def _load_mock_catalog() -> tuple[DiagnosticCatalogItem, ...]:
    payload = json.loads(_MOCK_PATH.read_text())
    items: list[DiagnosticCatalogItem] = []
    for row in payload.get("test_groups") or []:
        items.append(_from_record(row, kind=CatalogItemKind.test_group))
    for row in payload.get("packages") or []:
        items.append(_from_record(row, kind=CatalogItemKind.package))
    return tuple(items)


def load_diagnostic_catalog() -> list[DiagnosticCatalogItem]:
    health = (settings.health_provider or "mock").strip().lower()
    if health in {"supershyft", "postgres", "readonly"} and (settings.supershyft_database_url or "").strip():
        from integrations.supershyft.diagnostics import fetch_supershyft_catalog

        live = fetch_supershyft_catalog()
        if live:
            return live
    return list(_load_mock_catalog())
