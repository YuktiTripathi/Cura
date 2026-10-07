"""Readiness plan 3.8: the same question routes the same way in every language.

Each case is one question in English plus six languages. The deterministic planner's
routing for every translation is compared with the English one, and agreement is
reported per language. Targets are proposals; raise them as the planner improves.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pytest

from app.pipeline.indic_terms import canonicalize_biomarker_terms
from app.pipeline.query_planner import build_query_plan

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "language_parallel_eval.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
LANGUAGES = ("hi", "hinglish", "mr", "pa", "gu", "bn")

# Proposed minimum agreement per language with the English routing.
TARGET = {lang: 0.9 for lang in ("hi", "hinglish", "mr", "pa", "gu", "bn")}


def routing(message: str) -> dict:
    # Same normalization the chat pipeline applies before planning.
    plan = build_query_plan(canonicalize_biomarker_terms(message))
    return {
        "personal": bool(plan.needs_supershyft or plan.needs_blood or plan.needs_bio_ai),
        "history": bool(plan.history),
        "bio_ai": bool(plan.needs_bio_ai),
        "metrics": sorted(plan.requested_metrics or []),
    }


def agreement() -> tuple[dict[str, float], dict[str, list]]:
    hits: dict[str, list[bool]] = defaultdict(list)
    misses: dict[str, list] = defaultdict(list)
    for case in CASES:
        expected = routing(case["en"])
        for lang in LANGUAGES:
            got = routing(case[lang])
            ok = got == expected
            hits[lang].append(ok)
            if not ok:
                misses[lang].append((case["id"], expected, got))
    return {lang: sum(v) / len(v) for lang, v in hits.items()}, misses


def test_every_case_has_all_languages():
    for case in CASES:
        assert all(case.get(lang) for lang in ("en", *LANGUAGES)), case["id"]


@pytest.mark.parametrize("language", LANGUAGES)
def test_routing_agrees_with_english(language):
    scores, misses = agreement()
    assert scores[language] >= TARGET[language], f"{language} {scores[language]:.0%} misses={misses[language]}"
