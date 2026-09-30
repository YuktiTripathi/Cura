"""Deterministic catalog matching. Inventory never feeds medical reasoning."""

from __future__ import annotations

from app.contracts.diagnostics import (
    CatalogItemKind,
    DiagnosticCatalogItem,
    PackageCandidate,
    PackageCoverage,
)
from app.pipeline.diagnostic_catalog import load_diagnostic_catalog
from app.pipeline.lab_parameters import display_name_for


def _active(item: DiagnosticCatalogItem) -> bool:
    status = (item.status or "active").strip().lower()
    return status in {"active", "available", ""}


class PackageMatcher:
    def __init__(self, catalog: list[DiagnosticCatalogItem] | None = None):
        self._catalog = catalog

    def catalog(self) -> list[DiagnosticCatalogItem]:
        return list(self._catalog) if self._catalog is not None else load_diagnostic_catalog()

    def match(
        self,
        requested: list[str],
        *,
        require_all: bool = False,
        name_query: str | None = None,
    ) -> list[PackageCandidate]:
        wanted = [key for key in dict.fromkeys(requested or []) if key]
        if not wanted and not name_query:
            return []
        candidates: list[PackageCandidate] = []
        for item in self.catalog():
            if not _active(item):
                continue
            included = set(item.included_tests)
            matched = [key for key in wanted if key in included] if wanted else []
            if wanted and not matched:
                continue
            if require_all and wanted and len(matched) < len(wanted):
                continue
            if name_query and name_query.lower() not in item.display_name.lower():
                if wanted and not matched:
                    continue
            coverage = PackageCoverage(
                requested=len(wanted) or len(included),
                matched=len(matched) if wanted else len(included),
                coverage_score=(len(matched) / len(wanted) if wanted else 1.0),
                matched_entities=matched,
                missing_entities=[key for key in wanted if key not in included],
            )
            candidates.append(PackageCandidate(item=item, coverage=coverage, available=True))
        return sorted(candidates, key=self._rank)

    def best(self, requested: list[str], *, require_all: bool = False) -> PackageCandidate | None:
        ranked = self.match(requested, require_all=require_all)
        return ranked[0] if ranked else None

    def find_containing(self, entity: str) -> list[PackageCandidate]:
        return self.match([entity])

    @staticmethod
    def _rank(candidate: PackageCandidate) -> tuple:
        item = candidate.item
        extra = max(0, len(item.included_tests) - candidate.coverage.matched)
        kind_penalty = 0 if item.kind == CatalogItemKind.test_group else 1
        price = item.price if item.price is not None else 10**9
        return (
            -candidate.coverage.coverage_score,
            extra,
            kind_penalty,
            len(item.included_tests),
            price,
            item.display_name.lower(),
        )


def coverage_labels(candidate: PackageCandidate) -> list[str]:
    labels: list[str] = []
    for key in candidate.coverage.matched_entities:
        labels.append(candidate.item.included_test_labels.get(key) or display_name_for(key))
    return labels
