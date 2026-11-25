# Content registry specification

Reviewed educational content already lives in the repository. Screen builders read it. They do not ask a model to regenerate it.

## Sources of truth

| Content | Path | Used for |
| --- | --- | --- |
| Category names, order, one-line descriptions | `backend/app/biomarkers/health_categories.py` | Overview cards |
| Biomarker purpose, high, low, next step, common factors | `backend/app/biomarkers/data/biomarker_education_v1.json` via `education.py` | Biomarker detail `EducationNote` |
| Canonical names and system ids | `backend/app/biomarkers/registry.py`, `systems.py`, `data/registry_overlay_v1.json` | Joining provider codes to categories |
| Risk names and plain descriptions | `backend/app/biomarkers/data/risk_registry_v1.json` | Bio-AI detail |
| Related markers | `backend/app/retrieval/config/cura_biomarker_relationship_map.json` | "Related" list, filtered to markers this member has |
| Longer articles | `backend/app/retrieval/content/cura_biomarkers.json`, `cura_bio_ai_conditions.json`, `content/markdown/` | Conversation retrieval only, and only for entities in scope |
| Relationship and action hints | `backend/app/health_explanation/knowledge/relationships.json`, `actions.json` | May support chat. Not a second overview generator. |

`REGISTRY_VERSION` in `health_categories.py` is `unified-1`. Snapshot cache keys include it so a registry edit does not serve stale category copy.

## Rules

1. If a string exists in the education file or risk registry, the screen shows that string.
2. If a biomarker has no education entry, the screen shows the measured result and status and leaves purpose blank.
3. Category `about` text in `health_categories.py` is the overview description. `unified_wording.py` must not replace it on the screen path.
4. Related biomarkers are registry links intersected with the member snapshot. Missing related tests are omitted, not invented.
5. Retrieval for chat may attach the registry entry for the resolved entities. It must not attach the full knowledge base.
6. Articles are general education. They are not interpreted as this member's diagnosis.
7. Locale: English registry text ships first. UI chrome uses `frontend/src/i18n`. Translating clinical registry strings needs a reviewer; machine translation is not part of Phase 1.

## Status copy

Status labels are application constants tied to `FindingStatus` in `unified_health.py`, computed by `unified_overview.py` from report flags and numeric ranges. They are not free-form model text.

Measured language and predicted language stay different. A risk classification is never labelled as a blood result, and a blood status is never labelled as a Bio-AI prediction.

## Ownership

Changes to education JSON and risk registry JSON are content changes. They require the same review as a medical copy edit. Code that loads them stays in `backend/app/biomarkers/`.
