# Health Explanation Layer: how the spec maps to Cura

The HEL spec is built on top of the existing unified overview. It does not add a second pipeline, database or service.
Status tags: DONE, PARTIAL, NOT STARTED. Nothing here has had clinical review. Rules and actions are marked `rule_based_unreviewed`.

| Spec section | Where it lives | Status |
|---|---|---|
| Data classification (measured, predicted) | `Finding.source_type`, Bio-AI kept apart from blood | DONE. Questionnaire data is not ingested. |
| Data quality statuses | `Finding.data_quality` (verified, reference_unavailable, unavailable) derived from the report | PARTIAL. needs_review, outdated, conflicting, invalid are not produced. |
| Finding engine, categories | `biomarkers/unified_overview.py`, `health_categories.py` (registry unified-1) | DONE |
| Relationship engine, approved rules only | `health_explanation/relationship_engine.py`, `knowledge/relationships.json` (rel-1), `causal_claim` always false | PARTIAL. Four contrasts and two marker groups. temporal_change and independent not produced. |
| Prioritization, rule based | `decide_status`, `_rank`, `urgent_threshold_hit`; tier then registry order, no severity score | DONE. Four levels exist as needs closer attention, worth attention, looking good, not assessed. |
| Explanation generation | `pipeline/unified_wording.py` (rules first, model optional, numbers guarded) | DONE for summary and interpretation. |
| Approved action engine | `knowledge/actions.json` (act-1). The model can no longer write or add actions. | DONE. Library is five conversation or tracking steps, none names a medicine, supplement or dose. |
| Overall summary | `UnifiedOverview.totals`, separate counts, no health score. Metabolic age is shown only when the report supplies it. | DONE |
| Longitudinal engine | previous values exist on some results | NOT STARTED |
| Validation and safety | `health_explanation/safety_validator.py` rejects diagnosis, cause, rules out, dose or medicine, probability. A failing field falls back to rules wording. | PARTIAL. Pattern check, no second regeneration pass. |
| Output contract | `UnifiedOverview`, `CategoryDetail`, `Finding`, `Relationship`, `limitations`, `versions` | DONE |
| Endpoints | `/api/v1/health-explanation/` overview, categories/{id}, findings/{id}, refresh. timeline is not built. | PARTIAL |
| Caching | wording cache key includes member and report content; refresh recomputes | DONE |
| Privacy and isolation | no member id in any path, principal decides whose data is read, tests added | DONE for the endpoints |
| Frontend | area screen shows relationship wording and the overview shows what could not be covered | PARTIAL |
| Metrics, Hindi | | NOT STARTED |

## Blocking before release
1. Clinical review of the relationship rules, the action library, status rules and all wording.
2. Confirm the production Bio-AI label strings and thresholds.
3. Decide whether Increased Risk plus an out of range result counts as needing closer attention.
