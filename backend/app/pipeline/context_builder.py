from uuid import uuid4

from app.auth.models import AuthenticatedPrincipal
from app.contracts.common import IntentType, MarkerFlag
from app.contracts.evidence import EvidenceRecord
from app.contracts.health_context import (
    DisambiguationCandidate,
    HealthContext,
    InRangeSummary,
    MissingItem,
)
from app.contracts.query import QueryPlan
from app.contracts.user import UserProfile
from app.pipeline.trend_engine import comparison
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
from app.pipeline.lab_parameters import display_name_for, related_keys
from app.pipeline.health_scenario import HealthScenarioEngine
from app.pipeline.recommendation_engine import RecommendationEngine
from app.pipeline.personal_profile import build_personal_profile
from app.pipeline.health_timeline import build_health_timeline
from app.pipeline.goal_progress import compute_goal_progress
from app.pipeline.fact_envelope import bio_risk_fact, comparison_facts, marker_fact, recommendation_facts
from app.providers.registry import ProviderRegistry
from app.retrieval.result import HealthRetrievalResult
from app.retrieval.router import HealthRetrievalRouter


def _find_risk(risks, code):
    options = _bio_code_options(code)
    return next((item for item in risks if (item.code or "").lower() in options), None)


class ContextBuilder:
    def __init__(self, registry: ProviderRegistry):
        self.registry = registry
        self.retrieval = HealthRetrievalRouter(registry)

    def build(
        self,
        principal: AuthenticatedPrincipal,
        plan: QueryPlan,
        *,
        db=None,
        document_ids: list[str] | None = None,
        retrieval: HealthRetrievalResult | None = None,
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
                principal, plan, db=db, document_ids=document_ids
            )
        ctx = HealthContext(
            intent=plan.intent,
            answer_depth=plan.answer_depth,
            knowledge_scope=plan.knowledge_scope,
            data_source="supershyft" if personal else "general",
            resolved_topic=plan.topic,
            resolved_topic_name=plan.topic_name,
            display_name=profile.display_name or None,
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
            self._attach_personalization(
                ctx,
                principal,
                plan,
                blood_reports=scenario_input.blood_reports,
                bio_reports=scenario_input.bio_ai_reports,
                db=db,
                user=profile,
            )
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
        if plan.needs_bio_ai:
            self._fill_bio(ctx, plan, bio_reports, evidence)
        if plan.needs_lifestyle or plan.needs_profile:
            if retrieval and retrieval.ihr_called:
                life = retrieval.lifestyle
            else:
                life = self.registry.lifestyle.query(principal, plan)
            ctx.lifestyle = life
            if life and life.notes:
                ctx.notes.extend(life.notes)

        if plan.intent == IntentType.nutrition_guidance:
            engine = RecommendationEngine()
            result = engine.validate(engine.deterministic_candidates(ctx), ctx)
            ctx.recommendations = result.approved

        if personal:
            ctx.meta.sources = ["supershyft"]
        if retrieval and retrieval.document_evidence:
            evidence.extend(retrieval.document_evidence)
            ctx.meta.sources = list(dict.fromkeys([*(ctx.meta.sources or []), "uploaded_document"]))
            if retrieval.document_evidence and not ctx.markers:
                from app.contracts.blood import BloodMarker
                from app.contracts.common import MarkerFlag

                ctx.markers = [
                    BloodMarker(
                        id=ev.evidence_id,
                        key=(ev.marker or "").lower().replace(" ", "_"),
                        name=ev.marker or "marker",
                        value=ev.value,
                        unit=ev.unit,
                        flag=MarkerFlag.unknown,
                        source="user_uploaded",
                        report_id=ev.report_id,
                    )
                    for ev in retrieval.document_evidence
                    if ev.value is not None
                ]
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
        )
        return ctx

    def _fill_blood(self, ctx, plan, reports, evidence):
        if not reports:
            ctx.missing.append(MissingItem(key=plan.topic or "blood", name=plan.topic_name or "blood", reason="no_reports"))
            return
        keys = wanted_metric_keys(plan)
        expanded: list[str] = []
        for key in keys:
            for item in related_keys(key) or {key}:
                if item not in expanded:
                    expanded.append(item)
        keys = expanded or keys
        operation = plan.time_operation or "latest_marker"

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
                comparisons.append(
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
                evidence.append(self._ev(prev_report.report_id, "blood_report", prev_report.report_date, prev_m.name, None, prev_m))
                evidence.append(self._ev(curr_report.report_id, "blood_report", curr_report.report_date, curr_m.name, None, curr_m))
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
        if plan.topic in {"glucose", "fasting_blood_glucose"}:
            fasting = [item for item in selected if item.key == "fasting_blood_glucose"]
            if fasting:
                selected = fasting
                missing = [item for item in missing if item != "fasting_blood_glucose"]
        if not selected and not keys:
            report = latest_report(reports)
            selected = list(report.markers) if report else []
        ctx.markers = selected
        for marker in selected:
            report = next((item for item in reports if item.report_id == marker.report_id), reports[-1])
            evidence.append(self._ev(report.report_id, "blood_report", report.report_date, marker.name, None, marker))
        for key in missing:
            ctx.missing.append(MissingItem(key=key, name=display_name_for(key), reason="not_in_reports"))

    def _fill_bio(self, ctx, plan, reports, evidence):
        if not reports:
            ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name=plan.topic_name or "Bio-AI", reason="no_reports"))
            return
        codes = [key for key in (plan.requested_metrics or ([plan.topic] if plan.topic else [])) if key]
        codes = [code for code in codes if code not in {"metabolic_age", "metabolic_score"}]
        unique_dates = {r.report_date for r in reports}

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
                    ctx.bio_ai_risks.append(ra)
                    evidence.append(self._ev(previous.report_id, "bio_ai_report", previous.report_date, ra.name, ra.code))
                if rb:
                    ctx.bio_ai_risks.append(rb)
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

        if plan.intent == IntentType.bio_ai_score and len(reports) > 1 and len(unique_dates) == 1:
            found_requested = (
                any(select_bio_risks(report, codes)[0] for report in reports) if codes else True
            )
            if found_requested:
                ctx.status = "ambiguous"
                ctx.disambiguation = [
                    DisambiguationCandidate(
                        report_id=r.report_id,
                        report_date=r.report_date,
                        source_line=r.source_line,
                        label=r.source_line,
                    )
                    for r in reports
                ]
                risks = []
                for report in reports:
                    selected, missing = select_bio_risks(report, codes)
                    chosen = selected if codes else list(report.risks)
                    risks.extend(chosen)
                    for rk in chosen:
                        evidence.append(self._ev(report.report_id, "bio_ai_report", report.report_date, rk.name, rk.code))
                    for code in missing:
                        ctx.missing.append(MissingItem(key=code, name=display_name_for(code), reason="score_not_available"))
                ctx.bio_ai_risks = risks
                return

        if plan.intent == IntentType.bio_ai_explanation:
            previous = previous_bio_report(reports)
            latest = latest_bio_report(reports)
            if latest is None:
                ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name=plan.topic_name or "Bio-AI", reason="no_reports"))
                return
            selected, missing = select_bio_risks(latest, codes)
            ctx.bio_ai_risks = selected
            ctx.metabolic_age = latest.metabolic_age
            ctx.metabolic_score = latest.metabolic_score
            for rk in selected:
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

        report = latest_bio_report(reports)
        if report is None:
            ctx.missing.append(MissingItem(key=plan.topic or "bio_ai", name=plan.topic_name or "Bio-AI", reason="no_reports"))
            return
        selected, missing = select_bio_risks(report, codes)
        ctx.bio_ai_risks = selected
        ctx.metabolic_age = report.metabolic_age
        ctx.metabolic_score = report.metabolic_score
        for rk in selected:
            evidence.append(self._ev(report.report_id, "bio_ai_report", report.report_date, rk.name, rk.code))
        for code in missing:
            ctx.missing.append(MissingItem(key=code, name=display_name_for(code), reason="score_not_available"))

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
        ctx.profile = build_personal_profile(
            user=user,
            lifestyle=ctx.lifestyle,
            bio_risks=ctx.bio_ai_risks,
            goals=goals,
            user_facts=user_facts,
        )
        ctx.timeline = build_health_timeline(
            subject_id=principal.subject_id,
            blood_reports=blood_reports or [],
            bio_reports=bio_reports or [],
            documents=documents,
        )
        facts = [marker_fact(marker, principal.subject_id) for marker in ctx.markers]
        facts.extend(bio_risk_fact(risk, principal.subject_id) for risk in ctx.bio_ai_risks)
        for row in ctx.comparisons:
            facts.extend(comparison_facts(row, principal.subject_id))
        if ctx.profile:
            facts.extend(ctx.profile.dietary_preferences)
            facts.extend(ctx.profile.allergies)
            facts.extend(ctx.profile.health_goals)
            facts.extend(ctx.profile.lifestyle)
        facts.extend(recommendation_facts(ctx.recommendations))
        ctx.facts = facts
        if plan.intent == IntentType.health_goal_progress and not goals:
            ctx.missing.append(MissingItem(key="health_goals", name="health goals", reason="no_goals"))

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
