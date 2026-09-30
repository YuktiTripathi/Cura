# Longitudinal personalization

CURA reuses existing profile, goals, lifestyle, questionnaire, timeline, and trend machinery. Personalization is an overlay, not a second source of truth.

```
HealthContext (authoritative labs, goals, lifestyle, questionnaire)
→ PersonalizationContext          (summary + session communication/recent context)
→ PersonalBaseline / longitudinal classes
→ HealthStory + quiet-mode + journey DTO
→ reasoner prompt (compact history only)
→ presentation (themes, clinician handoff, package card)
```

## Durable vs session

| Durable | Session / conversation |
| --- | --- |
| Stored goals (`GoalStore`) | “My goal is improving energy” until saved |
| Diet/activity/sleep from profile or questionnaire | “I feel feverish today” |
| Long-term preferences | Current topic, last biomarker, expected reply |

Conversational statements are never written as laboratory facts.

## Added modules

| Role | Path |
| --- | --- |
| Overlay DTO | `backend/app/contracts/personalization.py` |
| Builder | `backend/app/pipeline/personalization_context.py`, `personalization_layer.py` |
| Baselines | `backend/app/pipeline/baselines.py` |
| Compact history | `backend/app/pipeline/longitudinal.py` |
| Story / quiet / ranking | `health_story.py`, `quiet_mode.py`, `priority.py` |
| Insights / handoff / journey | `proactive_insights.py`, `clinician_handoff.py`, `journey.py` |
| Recent context | `recent_context.py` |

## Operations and modes

- `ASSESS_GOAL_PROGRESS` — existing goal progress, now with improving/stable/worsening/missing metrics.
- `PREPARE_CLINICIAN_DISCUSSION` / `CLINICIAN_HANDOFF` — structured notes, not a diagnosis.
- `QUIET_UPDATE` — only for explicit stability questions such as “do I need to change anything?”, and only when there is no meaningful trend, new abnormality, or acute context. It never rewrites a high/abnormal selector or a domain-specific answer.
- Domain questions (`How is my liver?`) stay `DOMAIN_SUMMARY`. Optional reasoning context (BMI, waist, lifestyle) is not retrieved or required in the visible answer.

## Package recommendations

Existing PackageCatalog matching is unchanged. Personalization adds why the option matters for this user, what is already recent, and what would be new (`recently_available`, `missing`, `stale`, `new_information`).
