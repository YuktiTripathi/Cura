# SuperShyft adapters

Cura keeps **two databases**:

| Role | Env var | Writes |
| --- | --- | --- |
| Cura conversations / audit | `DATABASE_URL` (SQLite) | yes |
| SuperShyft health data | `SUPERSHYFT_DATABASE_URL` | **never** |

Set `HEALTH_PROVIDER=supershyft` to read:

- `users`
- `individual_health_report.blood_parameters`
- `individual_health_report.reports` (Bio-AI / Metsights JSON)
- `user_preferences` (nutrition notes only)

Identity for health rows is SuperShyft `users.user_id`. In mock auth, send:

`X-Cura-User-Id: 123`

where `123` is that numeric id.

If Postgres is unreachable, chat will fail for health queries — switch `HEALTH_PROVIDER=mock` to demo offline.
