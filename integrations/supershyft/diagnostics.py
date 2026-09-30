"""Read-only SuperShyft diagnostic catalog. SELECT only; never Healthians or booking writes."""

from __future__ import annotations

import time

from sqlalchemy import text

from app.contracts.diagnostics import CatalogItemKind, DiagnosticCatalogItem
from app.core.config import settings
from app.pipeline.lab_parameters import canonicalize_marker_name, display_name_for
from integrations.supershyft.db import run_readonly

_PACKAGE_SELECT = text(
    """
    SELECT
        dp.diagnostic_package_id AS catalog_id,
        dp.package_name AS display_name,
        CAST(dp.diagnostic_provider AS TEXT) AS provider,
        dp.price,
        CAST(dp.status AS TEXT) AS status,
        CAST(dp.gender_suitability AS TEXT) AS gender_suitability,
        CAST(dp.collection_type AS TEXT) AS collection_type,
        hp.parameter_key,
        hp.test_name,
        hp.is_available
    FROM diagnostic_package dp
    JOIN diagnostic_package_test_groups dptg
      ON dptg.diagnostic_package_id = dp.diagnostic_package_id
    JOIN diagnostic_test_group_tests dtgt
      ON dtgt.group_id = dptg.group_id
    JOIN health_parameters hp
      ON hp.test_id = dtgt.test_id
    WHERE CAST(dp.status AS TEXT) = 'active'
    ORDER BY dp.diagnostic_package_id, dtgt.display_order NULLS LAST, hp.test_id
    """
)

_GROUP_SELECT = text(
    """
    SELECT
        dtg.group_id AS catalog_id,
        dtg.group_name AS display_name,
        dtg.price,
        CAST(dtg.gender_suitability AS TEXT) AS gender_suitability,
        hp.parameter_key,
        hp.test_name,
        hp.is_available
    FROM diagnostic_test_groups dtg
    JOIN diagnostic_test_group_tests dtgt
      ON dtgt.group_id = dtg.group_id
    JOIN health_parameters hp
      ON hp.test_id = dtgt.test_id
    ORDER BY dtg.group_id, dtgt.display_order NULLS LAST, hp.test_id
    """
)

_cache: tuple[float, list[DiagnosticCatalogItem]] | None = None
_CACHE_TTL = 60.0


def reset_diagnostics_cache() -> None:
    global _cache
    _cache = None


def _canonical_key(parameter_key: str | None, test_name: str | None) -> str | None:
    raw = (parameter_key or test_name or "").strip()
    if not raw:
        return None
    key = canonicalize_marker_name(raw)
    return key or None


def _accumulate(rows: list[dict], *, kind: CatalogItemKind, default_provider: str | None) -> list[DiagnosticCatalogItem]:
    buckets: dict[str, dict] = {}
    for raw in rows:
        available = raw.get("is_available")
        if available is False:
            continue
        key = _canonical_key(raw.get("parameter_key"), raw.get("test_name"))
        if not key:
            continue
        catalog_id = str(raw.get("catalog_id"))
        bucket = buckets.setdefault(
            catalog_id,
            {
                "catalog_id": catalog_id,
                "kind": kind,
                "display_name": raw.get("display_name") or catalog_id,
                "provider": (raw.get("provider") or default_provider or None),
                "price": float(raw["price"]) if raw.get("price") is not None else None,
                "status": (raw.get("status") or "active"),
                "gender_suitability": raw.get("gender_suitability"),
                "collection_type": raw.get("collection_type"),
                "included": [],
                "labels": {},
            },
        )
        if key not in bucket["included"]:
            bucket["included"].append(key)
            label = (raw.get("test_name") or "").strip() or display_name_for(key)
            bucket["labels"][key] = label
    items: list[DiagnosticCatalogItem] = []
    for bucket in buckets.values():
        included = list(bucket["included"])
        items.append(
            DiagnosticCatalogItem(
                catalog_id=bucket["catalog_id"],
                kind=bucket["kind"],
                display_name=bucket["display_name"],
                provider=bucket["provider"] or "SuperShyft",
                included_tests=included,
                included_test_labels=bucket["labels"],
                price=bucket["price"],
                status=str(bucket["status"] or "active"),
                gender_suitability=bucket["gender_suitability"],
                collection_type=bucket["collection_type"],
                extra_test_count=len(included),
            )
        )
    return items


def fetch_supershyft_catalog() -> list[DiagnosticCatalogItem]:
    if not (settings.supershyft_database_url or "").strip():
        return []
    global _cache
    now = time.monotonic()
    if _cache and now - _cache[0] < _CACHE_TTL:
        return list(_cache[1])
    try:
        package_rows = run_readonly(_PACKAGE_SELECT, {}) or []
        group_rows = run_readonly(_GROUP_SELECT, {}) or []
    except Exception:
        return []
    packages = _accumulate(package_rows, kind=CatalogItemKind.package, default_provider="SuperShyft")
    groups = _accumulate(group_rows, kind=CatalogItemKind.test_group, default_provider="SuperShyft")
    items = [*groups, *packages]
    _cache = (now, items)
    return list(items)
