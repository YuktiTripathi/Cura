# Content 2.1 review record

The files under `backend/app/biomarkers/content/v2/` were copied from the reviewed package `cura_medical_content_v2` on 2026-11-24.

The product owner confirmed that clinical review, medical evidence verification, and an independent writing-quality review were completed and that the content is correct.

Runtime behaviour:

- Biomarker education is read from `content/biomarker_content.json` when the biomarker id or name matches.
- Bio-AI blurbs are read from `content/bio_ai_content.json` by risk id.
- If an entry is missing, the screen still shows the verified result and does not generate replacement text.
- The JSON files are stored as reviewed. Their internal `review_status` fields were not rewritten.
