# SuperShyft adapters

Cura keeps **two databases**:

| Role | Env var | Writes |
| --- | --- | --- |
| Cura conversations / audit | `DATABASE_URL` (SQLite) | yes |
| SuperShyft health data | `SUPERSHYFT_DATABASE_URL` | **never** |

Set `HEALTH_PROVIDER=supershyft` to read (all queries are `SELECT` scoped to the authenticated `user_id`):

| Cura data | SuperShyft tables |
| --- | --- |
| Profile | `users` |
| Blood labs | `participant_blood_bookings` joined through `engagement_participants` (`blood_parameters` + `blood_report_raw.digital_data`). Nested lab JSON inside `individual_health_report.reports` is still accepted when present. |
| Bio-AI / MetSights | `individual_health_report.reports` (`diseases`, `metabolic_age`, `metabolic_score`) |
| Questionnaire | `questionnaire_responses` → `assessment_instances` → `questionnaire_definitions` / `questionnaire_options` / `assessment_packages` |
| Lifestyle | `user_preferences` when present; otherwise diet / sleep / activity answers from the questionnaire tables |

Identity for health rows is SuperShyft `users.user_id`. In mock auth, send:

`X-Cura-User-Id: 123`

where `123` is that numeric id.

If Postgres is unreachable, chat will fail for health queries — switch `HEALTH_PROVIDER=mock` to demo offline.
