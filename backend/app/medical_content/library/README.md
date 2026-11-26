# CURA medical content 2.2

Standalone revision of the supplied library; no application changes. Run `python validate_content.py` for structural checks or `python validate_content.py --strict` for readiness gates. Strict mode is expected to fail until remaining issues are resolved. Workbook keys are local content references, not production IDs. See coverage_report.json, writing_quality_audit.json, evidence/medical_evidence_verification_report.json and CLINICAL_REVIEW_CHECKLIST.md.

Revision 2.3: lifestyle/ contains the staging questionnaire registry and draft relationships. IDs are staging IDs, not production question keys.

Revision 2.4: education upgrade of every entry. Rebuild with `python tools/education_upgrade/apply.py`, audit with `python tools/education_upgrade/audit.py`. Claim-level evidence is in evidence/claim_evidence_map.json. Nothing is clinically approved.
