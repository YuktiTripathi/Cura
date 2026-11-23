"""Relationships between findings, from approved rules only.

Every relationship comes from a rule in `knowledge/relationships.json`, carries that rule's id and rationale, and says
`causal_claim: false`. The model never creates a relationship. Rules are an engineering draft and are marked unreviewed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.contracts.unified_health import Finding, Relationship

_FILE = Path(__file__).parent / "knowledge" / "relationships.json"
_OUT = {"above_range", "below_range", "critical"}


@lru_cache(maxsize=1)
def rules() -> dict:
    return json.loads(_FILE.read_text(encoding="utf-8"))


def build_relationships(
    category_id: str,
    scenario: str,
    measured: list[Finding],
    risks: list[Finding],
    canonical_by_finding: dict[str, str | None],
) -> list[Relationship]:
    data = rules()
    version = data["rules_version"]
    out: list[Relationship] = []

    def make(rule: dict, finding_ids: list[str]) -> Relationship:
        return Relationship(
            relationship_id=f"{rule['rule_id']}:{category_id}",
            category=category_id,
            finding_ids=finding_ids,
            relationship_type=rule["relationship_type"],
            interpretation=rule["interpretation"],
            causal_claim=False,
            evidence_status="rule_based_unreviewed",
            rule_id=rule["rule_id"],
            rationale=rule["rationale"],
            rules_version=version,
        )

    # Findings of the same kind that are outside range and belong to one approved group.
    for rule in data["marker_group_rules"]:
        wanted = set(rule["markers"])
        hits = [f for f in measured if f.status in _OUT and canonical_by_finding.get(f.id) in wanted]
        if len(hits) >= rule["min_outside"]:
            out.append(make(rule, [f.id for f in hits]))

    # Measured results against predicted risks, only when both exist for the area.
    for rule in data["scenario_rules"]:
        if rule["scenario"] == scenario:
            ids = [f.id for f in measured if f.status in _OUT or f.status == "within_range"] + [f.id for f in risks if f.status != "risk_unknown"]
            out.append(make(rule, ids))
    return out
