# 2.2

- Preserved 330 entries and original identifiers.
- Replaced generic non-allergen factors and limitations, improved display names and questions.
- Expanded directed relationships, condition/category education and mock-field lifestyle drafts.
- Reset unsupported clinical and evidence statuses.
- Added audit reports and strict content-derived checks.
- Remaining work: independent review, full evidence verification, assay and production mapping confirmation.

## 2.3
Added staging questionnaire registry, candidate measurement mapping and lifestyle relationships. No clinical approval.

## 2.4 (education upgrade, 26 Nov 2026)
Rewrote every entry to the educational standard in place: factor explanations, maintenance, modifiable risk,
misconceptions, lab range versus clinical threshold notes, individual allergen content, Bio-AI band meaning
without invented methodology, category organ education, relationship readings and lifestyle explanations.
Claim-level evidence map added (93 of 6,392 claims supported by a page read; the rest candidate only).
All rows remain pending clinical review. See docs/cura_v2/MEDICAL_LIBRARY_2_4_EDUCATION_UPGRADE.md.

## 2.4 update (27 Nov 2026)
Chat uses the library under one rule in every environment (any row not rejected); the approval-based chat
setting was removed and no row was marked approved. Threshold notes reach chat only when a source page
supports them. 46 source pages read in all; 123 distinct claims supported. Retrieval is ranked within a
token budget set by question type.
