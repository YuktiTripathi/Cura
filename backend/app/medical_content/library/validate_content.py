"""Validate draft integrity; --strict also checks actual readiness blockers."""
import json, pathlib, sys, collections, re
from jsonschema import Draft202012Validator
r=pathlib.Path(__file__).parent
def load(p): return json.loads((r/p).read_text())
def check(ok,msg):
 if not ok: errors.append(msg)
errors=[]; blockers=[]
for f in r.rglob('*.json'):
 try: json.loads(f.read_text())
 except Exception as ex: errors.append(f'{f}: {ex}')
i=load('inventory/master_biomarker_inventory.json'); b=load('content/biomarker_content.json'); a=load('content/allergy_content.json'); c=b+a; e=load('evidence/content_sources.json'); ids={x['source_id'] for x in e}; keys={x['inventory_id'] for x in i}; by={x['inventory_id']:x for x in i}; cb={x['content_key']:x for x in c}; canonical={x['biomarker_id'] for x in i if x['biomarker_id']}; risks=load('content/bio_ai_content.json'); cats=load('content/health_category_content.json'); risk_ids={x['risk_id'] for x in risks}; cat_ids={x['health_category'] for x in cats}; modules=load('content/shared_education_modules.json'); rel=load('relationships/biomarker_relationships.json'); life=load('relationships/lifestyle_relationships.json'); cov=load('coverage_report.json'); audit=load('writing_quality_audit.json'); ev=load('evidence/medical_evidence_verification_report.json'); unresolved=load('inventory/unresolved_mappings.json'); index=load('inventory/biomarker_content_index.json'); packages=load('inventory/package_biomarker_mapping.json')
check(len(i)==330 and len(b)==119 and len(a)==211,'Inventory totals differ from baseline');check(len(keys)==len(i)==len(cb)==len(c) and keys==set(cb),'Duplicate or missing inventory/content keys');check(len(canonical)==sum(bool(x['biomarker_id']) for x in i),'Duplicate canonical ID');check(len(ids)==len(e),'Duplicate source IDs');check(len(risk_ids)==len(risks)==11 and len(cat_ids)==len(cats)==15,'Missing/duplicate risk or category IDs');check({x['inventory_id'] for x in unresolved}=={x['inventory_id'] for x in i if not x['biomarker_id']},'Unresolved mapping mismatch')
check(len(index)==len(keys) and {x['inventory_id'] for x in index}==keys,'Content index coverage');
for x in index:
 check(x['content_key'] in cb and x['biomarker_id']==cb[x['content_key']]['biomarker_id'],'Index mapping mismatch')
for sex in ('male','female'):check(set(packages[sex])=={x['inventory_id'] for x in i if x[sex+'_package']},f'{sex} package mismatch')
for path,rows in [('inventory_entry',i),('content_entry',c),('relationship',rel),('lifestyle',life),('risk',risks),('category',cats),('source',e)]:
 v=Draft202012Validator(load(f'schemas/{path}.schema.json'))
 for j,x in enumerate(rows):
  for err in v.iter_errors(x):errors.append(f'{path}[{j}]: {err.message}')
for x in c:
 k=x['content_key']; orig=by[k];check(x['biomarker_id']==orig['biomarker_id'] and orig['original_test_name'] in x['original_test_names'],f'{k}: identity mismatch');check(set(x['result_explanations'])==set(orig['applicable_result_states']),f'{k}: result states mismatch');check(set(x['suggested_questions'])==set(x['result_explanations']),f'{k}: question states mismatch');check(set(x['related_biomarkers'])<=canonical and set(x.get('related_content_keys',[]))<=keys,f'{k}: unknown related marker');check(set(x['source_ids'])<=ids and set(x.get('shared_module_ids',[]))<=set(modules),f'{k}: unknown source/module');check(x['health_category'] in cat_ids,f'{k}: unknown category');check(len(x['what_happens_inside_my_body'])>=4,f'{k}: short biological explanation');check(bool(x['possible_influencing_factors']) and bool(x['clinical_limitations']),f'{k}: missing factors/limitations');check(x['review_status']=='pending_clinical_review',f'{k}: unsupported approval');check('question_eligibility' in x,f'{k}: missing eligibility');
 for q in x.get('question_eligibility',{}).get('conditional_questions',[]):check(bool(q.get('question')) and set(q.get('requires_related_content_keys',[]))<=keys,f'{k}: invalid conditional question')
for x in rel:
 u,v=x['source_content_key'],x['related_content_key'];check(u in keys and v in keys and u!=v,'Invalid relationship endpoint');check(x['source_biomarker_id']==cb[u]['biomarker_id'] and x['related_biomarker_id']==cb[v]['biomarker_id'],f'{u}/{v}: canonical mismatch');check(set(x['source_ids'])<=ids,'Unknown relationship source')
check(len({(x['source_content_key'],x['related_content_key']) for x in rel})==len(rel),'Duplicate directed relationship')
for x in life:check(set(x['related_content_keys'])<=keys and set(x['related_risk_ids'])<=risk_ids and set(x['source_ids'])<=ids,'Invalid lifestyle reference')
for x in risks:check(set(x['relevant_biomarkers'])<=canonical and set(x['source_ids'])<=ids,'Invalid risk reference')
for x in cats:check(set(x['associated_biomarkers'])<=canonical and set(x['associated_bio_ai_risks'])<=risk_ids and set(x['source_ids'])<=ids,'Invalid category reference')
check(len(audit['entries'])==len(keys) and {x['content_key'] for x in audit['entries']}==keys,'Incomplete writing audit');check(cov['mapped']==len(canonical) and cov['unresolved_identifiers']==len(unresolved) and cov['draft_entries']==len(c) and cov['biomarker_relationships']==len(rel) and cov['lifestyle_relationships']==len(life),'Coverage report mismatch');check(not any(re.search(r'c[- ]suite',json.dumps(x),re.I) for x in c),'Disallowed user-facing terminology')
# Diagnostics distinguish legitimate shared allergy modules from suspicious identical non-allergen sections.
for field in ('what_happens_inside_my_body','possible_influencing_factors','clinical_limitations'):
 counts=collections.Counter(tuple(x[field]) for x in b)
 for val,n in counts.items():
  if n>1:blockers.append(f'{field}: {n} non-allergen entries share an identical section: {val[0]}')
if unresolved:blockers.append(f'{len(unresolved)} unresolved production canonical IDs')
assays=sum('assay_unconfirmed' in x['result_explanations'] for x in c)
if assays:blockers.append(f'{assays} entries require assay/result-format confirmation')
if any(x.get('verification')!='supported' for x in ev['sections']):blockers.append('Section-level medical evidence verification incomplete')
if any(not x['source_ids'] or x.get('evidence_status')!='verified' for x in rel+life+risks+cats):blockers.append('Supporting library evidence incomplete')
if not audit['independent_review_completed']:blockers.append('Independent semantic writing review incomplete')
if any('production definition requires confirmation' in x['field_provenance'] for x in life):blockers.append('Production questionnaire fields unconfirmed')
qreg=load('lifestyle/questionnaire_registry.json'); qids={x['question_id'] for x in qreg['questions']}
check(len(qids)==len(qreg['questions'])==91,'Questionnaire coverage mismatch')
check(all(set(x['question_ids'])<=qids for x in qreg['categories']),'Invalid category question references')
check(all(x['question_id'] in qids for x in life),'Invalid lifestyle question reference')
check({x['question_id'] for x in load('lifestyle/questionnaire_education.json')}==qids,'Missing questionnaire education')
check(all(set(x['candidate_content_keys'])<=keys for x in load('lifestyle/questionnaire_measurement_mapping.json')),'Invalid questionnaire measurement mapping')
blockers.append('Staging question keys and production equivalence unconfirmed')
if errors:
 print('\n'.join(errors));sys.exit(1)
print(f'Structural validation passed: {len(c)} entries, {len(canonical)} mapped IDs, {len(rel)} directed relationships.')
print('Readiness blockers:');print('\n'.join('- '+x for x in blockers))
if '--strict' in sys.argv and blockers:sys.exit(2)
