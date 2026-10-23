# CURA query reliability audit

Verified from the current pipeline (`service.py` chat, `routing/mapper.py` `plan_from_jev`, `query_planner.build_query_plan`, `response_planner.repair_report_level_plan`, `source_routing.apply_source_routing`, `context_builder`, `reasoning.reason`, `presentation.build_structured_response`).

## Current request flow

1. `ChatService.chat` normalizes the message and loads conversation state.
2. `RouteStage` calls Jev, then `plan_from_jev` maps the decision onto a `QueryPlan`.
3. `attach_task_plan` and `repair_report_level_plan` may narrow the plan.
4. `apply_source_routing` can turn a report phrase into an upload path when an uploaded file exists, or into general education when the utterance looks educational.
5. `ContextBuilder` retrieves only the sources flagged on the plan.
6. `ReasoningService` either renders a deterministic lookup or calls the answer model.
7. `build_structured_response` chooses cards, tables, or narrative.

## Verified defects

- "Check my blood report and tell which values are outside range" did not match the report-level repair (the pattern required "show/review" and "blood report" close together, and did not cover "outside range"). A plan with no blood source then told the user the report was unavailable.
- "What are my Bio-AI risk scores?" could stay on a blood lookup, so the UI showed biomarkers instead of risk scores.
- A discrepancy question ("enzymes normal but Bio-AI liver risk is high") was not required to fetch both sources.
- Theme ranking scored abnormal flags equally, so a clinically important HbA1c could rank below a milder lipid flag.

## Planned changes implemented with this audit

- `task_contract.py` records the required sources for those wordings and applies them after Jev without replacing Jev.
- Report-level repair now includes "check my blood report" and "which values are outside range".
- Glycemic and red-cell abnormalities get extra priority weight. This is an engineering heuristic and still needs clinical review before it is treated as a guideline.

## Compatibility

`QueryPlan.task_contract` is optional. Existing clients are unchanged.

## Tests

`tests/unit/test_task_contract.py` covers the blood-list, Bio-AI list, discrepancy, and diabetes-risk plans.
