from uuid import uuid4

from app.auth.models import AuthenticatedPrincipal
from app.contracts.bio_ai import BioAIRisk
from app.contracts.blood import BloodMarker
from app.contracts.common import IntentType, MarkerFlag
from app.contracts.evidence import EvidenceRecord
from app.contracts.health_context import (
    DisambiguationCandidate,
    HealthContext,
    InRangeSummary,
    MissingItem,
    SourceAvailability,
)
from app.contracts.query import QueryPlan
from app.contracts.user import UserProfile
from app.pipeline.trend_engine import comparison
from app.pipeline.bio_ai_selection import select_bio_ai_report
from app.pipeline.personal_selection import (
    latest_bio_report,
    latest_report,
    measurements_for_key,
    previous_bio_report,
    select_bio_risks,
    select_latest_markers,
    select_previous_markers,
    wanted_metric_keys,
    _bio_code_options,
)
from app.pipeline.health_domains import DOMAIN_CODES
from app.pipeline.lab_parameters import (
    FAMILY_QUERY_KEYS,
    canonicalize_marker_name,
    display_name_for,
    is_lab_key,
    related_keys,
)
from app.pipeline.derived import attach_derived_facts, attach_user_stated
from app.pipeline.health_scenario import HealthScenarioEngine
from app.pipeline.recommendation_engine import RecommendationEngine
from app.pipeline.personal_profile import build_personal_profile
from app.pipeline.health_timeline import build_health_timeline
from app.pipeline.goal_progress import compute_goal_progress
from app.pipeline.fact_envelope import bio_risk_fact, comparison_facts, marker_fact, recommendation_facts
from app.pipeline.context_merger import ContextMerger
from app.providers.registry import ProviderRegistry
from app.retrieval.result import HealthRetrievalResult
from app.pipeline.data import PersonalDataService
from app.pipeline.dev_trace import trace


def _availability(requested: bool, records: int, unavailable: bool = False) -> SourceAvailability:
    if not requested:
        return SourceAvailability(status="not_requested", records=0)
    if unavailable:
        return SourceAvailability(status="unavailable", records=0)
    if records:
        return SourceAvailability(status="available", records=records)
    return SourceAvailability(status="not_available", records=0)


def attach_source_status(
    ctx: HealthContext,
    plan: QueryPlan,
    retrieval: HealthRetrievalResult | None,
) -> None:
    blood_n = len(retrieval.blood_reports) if retrieval else len(ctx.markers)
    bio_n = len(retrieval.bio_ai_reports) if retrieval else len(ctx.bio_ai_risks)
    q_n = len(retrieval.questionnaire_instances) if retrieval else len(ctx.questionnaire_instances or ctx.questionnaire)
    doc_n = len(retrieval.documents) if retrieval else len(ctx.uploaded_documents)
    profile_n = 1 if ctx.profile else 0
    goal_n = len(ctx.goals or [])
    unavailable = bool(retrieval and retrieval.status == "provider_unavailable")
    ctx.source_status = {
        "blood": _availability(plan.needs_blood, blood_n, unavailable and plan.needs_blood),
        "bio_ai": _availability(plan.needs_bio_ai, bio_n, unavailable and plan.needs_bio_ai),
        "questionnaire": _availability(plan.needs_questionnaire, q_n, unavailable and plan.needs_questionnaire),
        "profile": _availability(plan.needs_profile or plan.needs_lifestyle, profile_n),
        "goals": _availability(plan.needs_goals, goal_n),
        "documents": _availability(plan.needs_user_uploaded, doc_n),
    }
    trace(
        "CONTEXT",
        personal_sources=[name for name, row in ctx.source_status.items() if row.status == "available"],
        missing_sources=[name for name, row in ctx.source_status.items() if row.status == "not_available"],
    )


def _selector_marker_flags(selectors: set[str]) -> set[MarkerFlag] | None:
    if "HIGH" in selectors:
        return {MarkerFlag.high, MarkerFlag.critical}
    if "LOW" in selectors:
        return {MarkerFlag.low, MarkerFlag.critical}
    if "ABNORMAL" in selectors:
        return {MarkerFlag.high, MarkerFlag.low, MarkerFlag.critical}
    if "NORMAL" in selectors:
        return {MarkerFlag.normal}
    return None


def _find_risk(risks, code):
    options = _bio_code_options(code)
    return next((item for item in risks if (item.code or "").lower() in options), None)


class ContextBuilder:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry
        self.retrieval = PersonalDataService(registry)

    def build(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        *,
        db=None,
        document_ids: list[str] | None = None,
        retrieval: HealthRetrievalResult | None = None,
        conversation_report_id: str | None = None,
        message: str | None = None,
        conversation_state=None,
    ) -> HealthContext:
        personal = plan.needs_personal_data
        profile = UserProfile(
            subject_id=principal.subject_id,
            display_name=principal.display_name or "",
        )
        if personal:
            profile = self.registry.users.get_profile(principal)
        if retrieval is None and (personal or plan.needs_user_uploaded):
            retrieval = self.retrieval.retrieve(
                principal, plan, db=db, document_ids=document_ids or plan.document_ids or []
            )
        ctx = HealthContext(
            intent=plan.intent,
            answer_depth=plan.answer_depth,
            knowledge_scope=plan.knowledge_scope,
            data_source="supershyft" if personal else "general",
            resolved_topic=plan.topic,
            resolved_topic_name=plan.topic_name,
            display_name=profile.display_name or None,
            requested_entity_codes=list(plan.requested_metrics or []),
            operations=list(plan.operations or []),
            question_type=plan.question_type,
            domains=list(plan.domains or []),
            selectors=list(plan.selectors or []),
            display_entity_codes=list(plan.display_entities or []),
            reasoning_context_codes=list(plan.reasoning_context or []),
        )
        evidence: list[EvidenceRecord] = []

        if not personal:
            ctx.evidence = evidence
            ctx.evidence_ids = []
            ctx.meta.sources = ["general"]
            return ctx

        if plan.intent == IntentType.health_scenario:
            scenario_input = self.registry.scenarios.query(principal, plan)
            ctx.scenario = HealthScenarioEngine().build(
                scenario_input.blood_reports,
                scenario_input.bio_ai_reports,
                scenario_input.lifestyle,
            )
            if scenario_input.blood_reports:
                ctx.markers = list(
                    sorted(
                        scenario_input.blood_reports,
                        key=lambda r: (r.report_date, r.report_id),
                    )[-1].markers
                )
            if scenario_input.bio_ai_reports:
                latest_bio = sorted(
                    scenario_input.bio_ai_reports,
                    key=lambda r: (r.report_date, r.report_id),
                )[-1]
                ctx.bio_ai_risks = list(latest_bio.risks)
                ctx.metabolic_age = latest_bio.metabolic_age
                ctx.metabolic_score = latest_bio.metabolic_score
            ctx.lifestyle = scenario_input.lifestyle
            if scenario_input.lifestyle:
                ctx.notes.extend(scenario_input.lifestyle.notes)
            ctx.evidence = list(ctx.scenario.evidence)
            ctx.evidence_ids = [e.evidence_id for e in ctx.evidence]
            ctx.meta.sources = ["supershyft"]
            ctx.meta.report_ids = list(dict.fromkeys(e.report_id for e in ctx.evidence))
            self._fill_questionnaire(ctx, principal, plan, retrieval)
            if retrieval:
                ctx.source_outcomes = list(retrieval.source_outcomes)
            self._attach_personalization(
                ctx,
                principal,
                plan,
                blood_reports=scenario_input.blood_reports,
                bio_reports=scenario_input.bio_ai_reports,
                db=db,
                user=profile,
                retrieval=retrieval,
                message=message,
                conversation_state=conversation_state,
            )
            attach_user_stated(ctx, plan)
            attach_derived_facts(ctx, plan)
            attach_source_status(ctx, plan, retrieval)
            return ctx

        if retrieval and retrieval.ihr_called:
            blood_reports = list(retrieval.blood_reports) if plan.needs_blood else []
            bio_reports = list(retrieval.bio_ai_reports) if plan.needs_bio_ai else []
        else:
            blood_reports = self.registry.blood.query(principal, plan) if plan.needs_blood else []
            bio_reports = self.registry.bio_ai.query(principal, plan) if plan.needs_bio_ai else []
        blood_reports = sorted(blood_reports, key=lambda r: (r.report_date, r.report_id))
        bio_reports = sorted(bio_reports, key=lambda r: (r.report_date, r.report_id))

        if plan.needs_blood:
            self._fill_blood(ctx, plan, blood_reports, evidence)
            self._fill_trends_if_needed(ctx, plan, blood_reports, evidence)
        if plan.needs_bio_ai:
            self._fill_bio(
                ctx,
                plan,
                bio_reports,
                evidence,
                conversation_report_id=conversation_report_id,
            )
        if retrieval:
            ctx.source_outcomes = list(retrieval.source_outcomes)
        if plan.needs_lifestyle or plan.needs_profile:
            if retrieval and retrieval.ihr_called:
                life = retrieval.lifestyle
            else:
                life = self.registry.lifestyle.query(principal, plan)
            ctx.lifestyle = life
            if life and life.notes:
                ctx.notes.extend(life.notes)

        self._fill_questionnaire(ctx, principal, plan, retrieval)

        if plan.intent == IntentType.nutrition_guidance:
            engine = RecommendationEngine()
            result = engine.validate(engine.deterministic_candidates(ctx, plan.requested_category), ctx)
            ctx.recommendations = result.approved

        if personal:
            ctx.meta.sources = ["supershyft"]
        if retrieval and retrieval.document_evidence:
            evidence.extend(retrieval.document_evidence)
            ctx.meta.sources = list(dict.fromkeys([*(ctx.meta.sources or []), "uploaded_document"]))
            document_markers = []
            for ev in retrieval.document_evidence:
                if ev.value is None:
                    continue
                key = canonicalize_marker_name(ev.marker or "") or (ev.marker or "").lower().replace(" ", "_")
                document_markers.append(
                    BloodMarker(
                        id=ev.evidence_id,
                        key=key,
                        name=ev.marker or "marker",
                        value=ev.value,
                        unit=ev.unit,
                        flag=MarkerFlag.unknown,
                        source="user_uploaded",
                        report_id=ev.document_id or ev.report_id,
                        measured_at=ev.report_date,
                    )
                )
            if document_markers and not ctx.markers:
                ctx.markers = document_markers
            elif document_markers and ctx.markers:
                ctx.notes.append(
                    "Uploaded document measurements are listed separately from SuperShyft values."
                )
        ctx.evidence = evidence
        ctx.evidence_ids = [e.evidence_id for e in evidence]
        if not ctx.meta.sources:
            ctx.meta.sources = ["supershyft"]
        ctx.meta.report_ids = list(dict.fromkeys(e.report_id for e in evidence))
        self._attach_personalization(
            ctx,
            principal,
            plan,
            blood_reports=blood_reports,
            bio_reports=bio_reports,
            db=db,
            user=profile,
            retrieval=retrieval,
            message=message,
            conversation_state=conversation_state,
        )
        attach_source_status(ctx, plan, retrieval)
        return ctx

    def _fill_blood(self, ctx, plan, reports, evidence):
        if not reports:
            ctx.missing.append(
                MissingItem(
                    key=plan.topic or "blood",
                    name=plan.topic_name or display_name_for(plan.topic or "") or "blood",
                    reason="no_reports",
                )
            )
            return
        keys = wanted_metric_keys(plan)
        operation = plan.time_operation or "latest_marker"
        ops = {str(item).upper() for item in (plan.operations or [])}
        selectors = {str(item).upper() for item in (plan.selectors or [])}
        if not keys and ops & {"SUMMARIZE", "PRIORITIZE", "IDENTIFY_GAPS"}:
            operation = "latest_report"
        if selectors & {"HIGH", "LOW", "ABNORMAL", "ALL", "NORMAL"} and (
            not keys or operation == "latest_report" or "overall_health" in (plan.domains or [])
        ):
            operation = "latest_report"
            keys = []
        specific_marker = plan.intent in {
            IntentType.latest_result,
            IntentType.blood_marker_explanation,
        } and len(keys) <= 1
        glucose_family = {"glucose", "fasting_blood_glucose", "postprandial_glucose"}
        if keys and set(keys) <= glucose_family:
            for item in related_keys("glucose"):
                if item not in keys:
                    keys.append(item)
        elif keys and not specific_marker:
            expanded: list[str] = []
            for key in keys:
                for item in related_keys(key) or {key}:
                    if item not in expanded:
                        expanded.append(item)
            keys = expanded or keys
        if "glucose" in keys and "fasting_blood_glucose" not in keys:
            keys.append("fasting_blood_glucose")

        if plan.intent == IntentType.health_goal_progress:
            report = latest_report(reports)
            if report is None:
                ctx.missing.append(MissingItem(key="blood", name="blood", reason="no_reports"))
                return
            ctx.markers = list(report.markers)
            in_r = sum(1 for m in report.markers if m.flag == MarkerFlag.normal)
            out_r = sum(1 for m in report.markers if m.flag in {MarkerFlag.low, MarkerFlag.high})
            miss = sum(1 for m in report.markers if m.flag == MarkerFlag.missing or m.value is None)
            ctx.in_range_summary = InRangeSummary(in_range=in_r, out_of_range=out_r, missing=miss)
            from collections import defaultdict

            history: dict[str, list] = defaultdict(list)
            for item in reports:
                for marker in item.markers:
                    if marker.value is not None:
                        history[marker.key].append((item, marker))
            for key, hits in history.items():
                if len(hits) < 2:
                    continue
                prev_report, prev_m = hits[-2]
                curr_report, curr_m = hits[-1]
                ctx.comparisons.append(
                    comparison(
                        key,
                        prev_m.value,
                        curr_m.value,
                        prev_report.report_id,
                        curr_report.report_id,
                        prev_report.report_date,
                        curr_report.report_date,
                    )
                )
            for m in report.markers:
                evidence.append(self._ev(report.report_id, "blood_report", report.report_date, m.name, None, m))
            return

        if plan.intent == IntentType.previous_result:
            selected, missing = select_previous_markers(reports, keys or [plan.topic] if plan.topic else [])
            if not selected:
                ctx.missing.append(MissingItem(key=plan.topic or "blood", name="previous result", reason="no_previous"))
                return
            ctx.markers = selected
            for marker in selected:
                report = next((item for item in reports if item.report_id == marker.report_id), reports[-2] if len(reports) > 1 else reports[0])
                evidence.append(self._ev(report.report_id, "blood_report", report.report_date, marker.name, None, marker))
            return

        if plan.intent == IntentType.trend:
            trend_keys = keys or ([plan.topic] if plan.topic else [])
            comparisons = []
            markers = []
            for key in trend_keys:
                hits = measurements_for_key(reports, key)
                if len(hits) < 2:
                    ctx.missing.append(MissingItem(key=key, name=display_name_for(key), reason="insufficient_history"))
                    continue
                prev, curr = hits[-2], hits[-1]
                prev_report, prev_m = prev
                curr_report, curr_m = curr
                if prev_m.key != curr_m.key:
                    continue
                markers.extend([prev_m, curr_m])
                item = comparison(
                    key,
                    prev_m.value,
                    curr_m.value,
                    prev_report.report_id,
                    curr_report.report_id,
                    prev_report.report_date,
                    curr_report.report_date,
                )
                comparisons.append(item)
                evidence.append(self._ev(prev_report.report_id, "blood_report", prev_report.report_date, prev_m.name, None, prev_m))
                evidence.append(self._ev(curr_report.report_id, "blood_report", curr_report.report_date, curr_m.name, None, curr_m))
                if plan.premise_claim and prev_m.value is not None and curr_m.value is not None:
                    from app.contracts.operations import PremiseCheck

                    increased = curr_m.value > prev_m.value
                    decreased = curr_m.value < prev_m.value
                    claimed_up = plan.premise_claim == "increased"
                    claimed_down = plan.premise_claim == "decreased"
                    verified = (claimed_up and increased) or (claimed_down and decreased)
                    if claimed_up and not increased:
                        verified = False
                    verb = {"increased": "increase", "decreased": "decrease"}.get(
                        plan.premise_claim, plan.premise_claim
                    )
                    ctx.premise = PremiseCheck(
                        claim=plan.premise_claim,
                        verified=verified,
                        note=(
                            None
                            if verified
                            else (
                                f"{display_name_for(key)} did not {verb}: "
                                f"{prev_m.value} on {prev_report.report_date} and {curr_m.value} on {curr_report.report_date}."
                            )
                        ),
                        previous_value=prev_m.value,
                        current_value=curr_m.value,
                        previous_date=prev_report.report_date,
                        current_date=curr_report.report_date,
                        previous_report_id=prev_report.report_id,
                        current_report_id=curr_report.report_id,
                    )
                    ctx.premise_verified = verified
            ctx.markers = markers
            ctx.comparisons = comparisons
            return

        if operation == "latest_report" or plan.intent in {
            IntentType.broad_health_summary,
            IntentType.report_explanation,
            IntentType.missing_data,
            IntentType.nutrition_guidance,
            IntentType.personal_profile,
        }:
            report = latest_report(reports)
            if report is None:
                ctx.missing.append(MissingItem(key=plan.topic or "blood", name=plan.topic_name or "blood", reason="no_reports"))
                return
            markers = list(report.markers)
            if keys:
                markers = [item for item in markers if item.key in keys]
            wanted_flags = _selector_marker_flags(selectors)
            if wanted_flags:
                markers = [item for item in markers if item.flag in wanted_flags]
            ctx.markers = markers
            in_r = sum(1 for m in markers if m.flag == MarkerFlag.normal)
            out_r = sum(1 for m in markers if m.flag in {MarkerFlag.low, MarkerFlag.high})
            miss = sum(1 for m in markers if m.flag == MarkerFlag.missing or m.value is None)
            if plan.intent != IntentType.latest_result:
                ctx.in_range_summary = InRangeSummary(in_range=in_r, out_of_range=out_r, missing=miss)
            for m in markers:
                evidence.append(self._ev(report.report_id, "blood_report", report.report_date, m.name, None, m))
                if plan.intent != IntentType.latest_result and (m.flag == MarkerFlag.missing or m.value is None):
                    ctx.missing.append(MissingItem(key=m.key, name=m.name))
            return

        selected, missing = select_latest_markers(reports, keys)
        optional = {item.lower() for item in (plan.optional_entities or [])}
        skip_missing = {
            *(plan.domains or []),
            "thyroid_function",
            "kidney_function",
            "liver_function",
            "thyroid",
            "lifestyle",
            "blood_pressure",
        }
        glucose_only = set(keys or []) <= {"glucose", "fasting_blood_glucose", "postprandial_glucose"}
        if plan.topic in {"glucose", "fasting_blood_glucose"} and glucose_only:
            fasting = [item for item in selected if item.key == "fasting_blood_glucose"]
            if fasting:
                selected = fasting
                missing = [item for item in missing if item != "fasting_blood_glucose"]
        if not selected:
            latest = latest_report(reports)
            for key in missing or keys:
                if key in skip_missing:
                    continue
                ctx.missing.append(
                    MissingItem(
                        key=key,
                        name=display_name_for(key),
                        reason="not_in_reports",
                        report_id=latest.report_id if latest else None,
                        report_date=latest.report_date if latest else None,
                        scope="optional" if key.lower() in optional else "latest blood report",
                    )
                )
            if not keys and not ctx.missing:
                ctx.missing.append(
                    MissingItem(
                        key=plan.topic or "requested_marker",
                        name=plan.topic_name or "that marker",
                        reason="not_in_reports",
                        report_id=latest.report_id if latest else None,
                        report_date=latest.report_date if latest else None,
                        scope="latest blood report",
                    )
                )
            ctx.markers = []
            return
        ctx.markers = selected
        latest = latest_report(reports)
        for key in missing:
            if key in skip_missing:
                continue
            ctx.missing.append(
                MissingItem(
                    key=key,
                    name=display_name_for(key),
                    reason="not_in_reports",
                    report_id=latest.report_id if latest else None,
                    report_date=latest.report_date if latest else None,
                    scope="optional" if key.lower() in optional else "latest blood report",
                )
            )
        for marker in selected:
            report = next((item for item in reports if item.report_id == marker.report_id), reports[-1])
            evidence.append(self._ev(report.report_id, "blood_report", report.report_date, marker.name, None, marker))

    def _fill_bio(self, ctx, plan, reports, evidence, conversation_report_id=None):
        if not reports:
            ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name=plan.topic_name or "Bio-AI", reason="no_reports"))
            return
        codes = [key for key in (plan.requested_metrics or ([plan.topic] if plan.topic else [])) if key]
        codes = [
            code
            for code in codes
            if code not in {"metabolic_age", "metabolic_score"}
            and not is_lab_key(code)
            and code not in DOMAIN_CODES
            and code not in FAMILY_QUERY_KEYS
        ]

        if plan.intent == IntentType.bio_ai_comparison:
            ctx.status = "ok"
            previous = previous_bio_report(reports)
            latest = latest_bio_report(reports)
            if previous is None or latest is None:
                ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name="Bio-AI comparison", reason="insufficient_history"))
                return
            compare_codes = codes or list(dict.fromkeys([*[rk.code for rk in previous.risks], *[rk.code for rk in latest.risks]]))
            ctx.bio_ai_risks = []
            ctx.comparisons = []
            for code in compare_codes:
                ra = _find_risk(previous.risks, code)
                rb = _find_risk(latest.risks, code)
                if ra is None and rb is None:
                    ctx.missing.append(MissingItem(key=code, name=display_name_for(code), reason="score_not_available"))
                    continue
                if ra:
                    ctx.bio_ai_risks.append(self._stamp_bio_risk(ra, previous))
                    evidence.append(self._ev(previous.report_id, "bio_ai_report", previous.report_date, ra.name, ra.code))
                if rb:
                    ctx.bio_ai_risks.append(self._stamp_bio_risk(rb, latest))
                    evidence.append(self._ev(latest.report_id, "bio_ai_report", latest.report_date, rb.name, rb.code))
                ctx.comparisons.append(
                    comparison(
                        code,
                        ra.score if ra else None,
                        rb.score if rb else None,
                        previous.report_id,
                        latest.report_id,
                        previous.report_date,
                        latest.report_date,
                    )
                )
            return

        if plan.intent == IntentType.bio_ai_explanation:
            previous = previous_bio_report(reports)
            latest = latest_bio_report(reports)
            if latest is None:
                ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name=plan.topic_name or "Bio-AI", reason="no_reports"))
                return
            selected, missing = select_bio_risks(latest, codes)
            ctx.bio_ai_risks = [self._stamp_bio_risk(rk, latest) for rk in selected]
            ctx.metabolic_age = latest.metabolic_age
            ctx.metabolic_score = latest.metabolic_score
            for rk in ctx.bio_ai_risks:
                evidence.append(self._ev(latest.report_id, "bio_ai_report", latest.report_date, rk.name, rk.code))
            for code in missing:
                ctx.missing.append(MissingItem(key=code, name=display_name_for(code), reason="score_not_available"))
            if previous is not None and codes:
                ctx.comparisons = []
                for code in codes:
                    ra = _find_risk(previous.risks, code)
                    rb = _find_risk(latest.risks, code)
                    if ra is None and rb is None:
                        continue
                    ctx.comparisons.append(
                        comparison(
                            code,
                            ra.score if ra else None,
                            rb.score if rb else None,
                            previous.report_id,
                            latest.report_id,
                            previous.report_date,
                            latest.report_date,
                        )
                    )
            return

        if plan.intent == IntentType.bio_ai_score:
            choice = select_bio_ai_report(
                reports,
                plan,
                message=plan.raw_message,
                conversation_report_id=conversation_report_id,
            )
            if choice.ambiguous:
                if codes and not any(select_bio_risks(report, codes)[0] for report in choice.ambiguous):
                    ctx.bio_ai_risks = []
                    for code in codes:
                        ctx.missing.append(MissingItem(key=code, name=display_name_for(code), reason="score_not_available"))
                    return
                ctx.status = "ambiguous"
                ctx.bio_ai_risks = []
                ctx.disambiguation = [self._bio_candidate(report) for report in choice.ambiguous]
                for report in choice.ambiguous:
                    selected, _missing = select_bio_risks(report, codes)
                    if codes:
                        for rk in selected:
                            evidence.append(
                                self._ev(report.report_id, "bio_ai_report", report.report_date, rk.name, rk.code)
                            )
                    else:
                        evidence.append(
                            self._ev(report.report_id, "bio_ai_report", report.report_date, None, None)
                        )
                return
            report = choice.report
        else:
            report = latest_bio_report(reports)
        if report is None:
            ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name=plan.topic_name or "Bio-AI", reason="no_reports"))
            return
        selected, missing = select_bio_risks(report, codes)
        ctx.bio_ai_risks = [self._stamp_bio_risk(rk, report) for rk in selected]
        ctx.metabolic_age = report.metabolic_age
        ctx.metabolic_score = report.metabolic_score
        for rk in ctx.bio_ai_risks:
            evidence.append(self._ev(report.report_id, "bio_ai_report", report.report_date, rk.name, rk.code))
        for code in missing:
            ctx.missing.append(MissingItem(key=code, name=display_name_for(code), reason="score_not_available"))

    def _stamp_bio_risk(self, risk, report):
        return risk.model_copy(
            update={
                "report_id": report.report_id,
                "measured_at": report.completed_at or report.report_date,
                "assessment_instance_id": report.assessment_instance_id,
            }
        )

    def _bio_candidate(self, report) -> DisambiguationCandidate:
        completed = report.completed_at
        if completed is None:
            completed_at = None
        elif hasattr(completed, "isoformat"):
            completed_at = completed.isoformat()
        else:
            completed_at = str(completed)
        return DisambiguationCandidate(
            report_id=report.report_id,
            report_date=report.report_date,
            source_line=report.source_line,
            label=report.source_line,
            assessment_instance_id=report.assessment_instance_id,
            completed_at=completed_at,
        )

    def _attach_personalization(
        self,
        ctx: HealthContext,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        *,
        blood_reports,
        bio_reports,
        db,
        user,
        retrieval: HealthRetrievalResult | None = None,
        message: str | None = None,
        conversation_state=None,
    ) -> None:
        goals = []
        user_facts = []
        documents = []
        if db is not None:
            from app.db.goal_store import GoalStore
            from app.documents.service import DocumentService

            store = GoalStore(db)
            goals = store.list_for_subject(principal.subject_id)
            user_facts = store.provided_facts(principal.subject_id)
            try:
                documents = DocumentService(db).list_for_user(principal.subject_id)
            except Exception:
                documents = []
        ctx.goals = goals
        ctx.goal_progress = compute_goal_progress(goals, blood_reports or [])
        if db is not None:
            from app.documents.uploaded_context import context_from_row

            ids = list(plan.document_ids or [])
            owned = []
            if ids:
                from app.db.models import Document as DocumentRow

                owned = (
                    db.query(DocumentRow)
                    .filter(
                        DocumentRow.user_id == principal.subject_id,
                        DocumentRow.id.in_(ids),
                        DocumentRow.upload_status != "deleted",
                    )
                    .all()
                )
            elif plan.needs_user_uploaded:
                from app.db.models import Document as DocumentRow
                from app.documents.metadata import load_meta

                candidates = (
                    db.query(DocumentRow)
                    .filter(
                        DocumentRow.user_id == principal.subject_id,
                        DocumentRow.upload_status != "deleted",
                    )
                    .order_by(DocumentRow.created_at.desc())
                    .limit(6)
                    .all()
                )
                owned = [
                    row
                    for row in candidates
                    if row.extraction_status == "completed" or load_meta(row).get("structured_facts_ready")
                ][:2]
            ctx.uploaded_documents = [context_from_row(row) for row in owned]
        ctx.profile = build_personal_profile(
            user=user,
            lifestyle=ctx.lifestyle,
            bio_risks=ctx.bio_ai_risks,
            goals=goals,
            user_facts=user_facts,
            questionnaire_answers=ctx.questionnaire,
        )
        ctx.timeline = build_health_timeline(
            subject_id=principal.subject_id,
            blood_reports=blood_reports or [],
            bio_reports=bio_reports or [],
            documents=documents,
            questionnaire_instances=ctx.questionnaire_instances,
        )
        facts = [marker_fact(marker, principal.subject_id) for marker in ctx.markers]
        uploaded_keys = {
            marker.key
            for marker in ctx.markers
            if (marker.source or "").lower() in {"user_uploaded", "uploaded_document"}
        }
        if retrieval and retrieval.document_evidence:
            for ev in retrieval.document_evidence:
                if ev.value is None:
                    continue
                key = canonicalize_marker_name(ev.marker or "") or (ev.marker or "").lower().replace(" ", "_")
                if key in uploaded_keys:
                    continue
                facts.append(
                    marker_fact(
                        BloodMarker(
                            id=ev.evidence_id,
                            key=key,
                            name=ev.marker or "marker",
                            value=ev.value,
                            unit=ev.unit,
                            flag=MarkerFlag.unknown,
                            source="user_uploaded",
                            report_id=ev.document_id or ev.report_id,
                            measured_at=ev.report_date,
                        ),
                        principal.subject_id,
                    ).model_copy(update={"document_id": ev.document_id, "page": ev.page_start})
                )
        facts.extend(bio_risk_fact(risk, principal.subject_id) for risk in ctx.bio_ai_risks)
        if ctx.metabolic_age is not None:
            report_id = next((risk.report_id for risk in ctx.bio_ai_risks if risk.report_id), None)
            facts.append(
                marker_fact(
                    BloodMarker(
                        id=f"metabolic-age-{report_id or 'latest'}",
                        key="metabolic_age",
                        name="metabolic age",
                        value=ctx.metabolic_age,
                        unit="years",
                        flag=MarkerFlag.unknown,
                        source="SuperShyft",
                        report_id=report_id,
                    ),
                    principal.subject_id,
                ).model_copy(update={"source_type": "supershyft_bio_ai", "notes": ["Bio-AI assessment, not a diagnosis"]})
            )
        for row in ctx.comparisons:
            facts.extend(comparison_facts(row, principal.subject_id))
        if ctx.profile:
            facts.extend(ctx.profile.dietary_preferences)
            facts.extend(ctx.profile.allergies)
            facts.extend(ctx.profile.health_goals)
            facts.extend(ctx.profile.lifestyle)
        facts.extend(answer.as_fact() for answer in ctx.questionnaire)
        facts.extend(recommendation_facts(ctx.recommendations))
        ctx.facts = facts
        ContextMerger().merge_into(ctx, plan, principal.subject_id)
        attach_user_stated(ctx, plan)
        attach_derived_facts(ctx, plan)
        if plan.intent == IntentType.health_goal_progress and not goals:
            ctx.missing.append(MissingItem(key="health_goals", name="health goals", reason="no_goals"))
        from app.pipeline.personalization_layer import attach_personalization_layer

        attach_personalization_layer(
            ctx,
            message=message or plan.raw_message or "",
            conversation_state=conversation_state,
            blood_reports=blood_reports or [],
        )
        from app.pipeline.conversation_experience import infer_conversation_goal, infer_response_depth
        from app.pipeline.relevant_context import RelevantContextSelector

        goal = infer_conversation_goal(message or plan.raw_message or "", plan, conversation_state)
        depth = infer_response_depth(message or plan.raw_message or "", plan, goal, conversation_state)
        selector = RelevantContextSelector()
        relevant = selector.select(
            ctx, plan, reports=blood_reports or [], goal=goal, depth=depth
        )
        selector.apply(ctx, relevant, reports=blood_reports or [], depth=depth)
        ctx.conversation_goal = goal.value
        ctx.response_depth = depth.value
        if conversation_state and conversation_state.explained_entities:
            ctx.explained_entities = list(conversation_state.explained_entities)

    def _fill_trends_if_needed(self, ctx, plan, reports, evidence) -> None:
        ops = {str(item).upper() for item in (plan.operations or [])}
        if not (plan.history or ops & {"TREND", "COMPARE", "VERIFY_PREMISE"}):
            return
        if ctx.comparisons or plan.intent == IntentType.trend:
            return
        keys = wanted_metric_keys(plan) or list(dict.fromkeys(m.key for m in ctx.markers if m.key))
        for key in keys:
            hits = measurements_for_key(reports, key)
            if len(hits) < 2:
                continue
            prev, curr = hits[-2], hits[-1]
            prev_report, prev_m = prev
            curr_report, curr_m = curr
            ctx.comparisons.append(
                comparison(
                    key,
                    prev_m.value,
                    curr_m.value,
                    prev_report.report_id,
                    curr_report.report_id,
                    prev_report.report_date,
                    curr_report.report_date,
                )
            )
            if plan.premise_claim and prev_m.value is not None and curr_m.value is not None and ctx.premise is None:
                from app.contracts.operations import PremiseCheck

                increased = curr_m.value > prev_m.value
                decreased = curr_m.value < prev_m.value
                verified = (plan.premise_claim == "increased" and increased) or (
                    plan.premise_claim == "decreased" and decreased
                )
                verb = {"increased": "increase", "decreased": "decrease"}.get(plan.premise_claim, plan.premise_claim)
                ctx.premise = PremiseCheck(
                    claim=plan.premise_claim,
                    verified=verified,
                    note=(
                        None
                        if verified
                        else (
                            f"{display_name_for(key)} did not {verb}: "
                            f"{prev_m.value} on {prev_report.report_date} and {curr_m.value} on {curr_report.report_date}."
                        )
                    ),
                    previous_value=prev_m.value,
                    current_value=curr_m.value,
                    previous_date=prev_report.report_date,
                    current_date=curr_report.report_date,
                    previous_report_id=prev_report.report_id,
                    current_report_id=curr_report.report_id,
                )
                ctx.premise_verified = verified

    def _ev(self, report_id, report_type, report_date, marker, risk_code, blood_marker=None) -> EvidenceRecord:
        rng = None
        value = None
        unit = None
        if blood_marker is not None:
            value = blood_marker.value
            unit = blood_marker.unit
            if blood_marker.reference_low is not None and blood_marker.reference_high is not None:
                rng = f"{blood_marker.reference_low:g}–{blood_marker.reference_high:g} {unit or ''}".strip()
        return EvidenceRecord(
            evidence_id=f"ev-{uuid4().hex[:8]}",
            report_id=report_id,
            report_type=report_type,
            report_date=report_date,
            marker=marker,
            risk_code=risk_code,
            source="ihr" if report_type in {"blood_report", "bio_ai_report"} else "supershyft",
            value=value,
            unit=unit,
            reference_range=rng,
        )

    def _fill_questionnaire(self, ctx, principal, plan, retrieval) -> None:
        if not plan.needs_questionnaire:
            return
        instances = []
        if retrieval is not None and retrieval.questionnaire_called:
            instances = list(retrieval.questionnaire_instances or [])
        else:
            provider = getattr(self.registry, "questionnaires", None)
            if provider is not None:
                instances = provider.query(principal, plan) or []
        ctx.questionnaire_instances = instances
        ctx.questionnaire = [answer for item in instances for answer in item.answers]
        if "questionnaire" not in (ctx.meta.sources or []):
            ctx.meta.sources = list(dict.fromkeys([*(ctx.meta.sources or []), "questionnaire"]))
        if not ctx.questionnaire:
            ctx.missing.append(
                MissingItem(key="questionnaire", name="questionnaire", reason="no_questionnaire_responses")
            )
