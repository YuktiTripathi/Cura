# Mapping (future)

| SuperShyft concept | Cura DTO field |
| --- | --- |
| authenticated member id | AuthenticatedPrincipal.subject_id |
| display name, age band, sex | UserProfile |
| analyte name/value/unit/ref/flag | BloodMarker |
| report id + collection date | BloodReport |
| Bio-AI risk code/score/status | BioAIRisk |
| Bio-AI vs Advanced Bio-AI | BioAIReport.source_line |
| metabolic age/score | BioAIReport |
| lifestyle summary | LifestyleContext |

Adapters must not leak Healthians or MetSights payloads into HealthContext.
