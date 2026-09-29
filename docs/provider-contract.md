# Provider contract

Adapters must return canonical Pydantic DTOs:

| Provider | Input | Output |
| --- | --- | --- |
| AuthProvider | HTTP request | AuthenticatedPrincipal |
| UserProfileProvider | principal | UserProfile |
| BloodReportProvider | principal, QueryPlan | list[BloodReport] |
| BioAIProvider | principal, QueryPlan | list[BioAIReport] |
| LifestyleProvider | principal, QueryPlan | LifestyleContext \| None |
| HealthScenarioProvider | principal | topic keys |

Do not pass raw vendor JSON into the pipeline. Filter by `principal.subject_id` inside the adapter.

Mock implementations live in `integrations/mock/` and are the Phase 1 default (`HEALTH_PROVIDER=mock`).
