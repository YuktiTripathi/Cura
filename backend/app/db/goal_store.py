from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.facts import FactKind, ProvenancedFact
from app.contracts.goals import ALLOWED_GOAL_CODES, GOAL_LABELS, GOAL_METRICS, HealthGoal
from app.core.errors import ValidationAppError
from app.db.models import UserHealthGoal, UserProfileFact


class GoalStore:
    def __init__(self, db: Session):
        self.db = db

    def list_for_subject(self, subject_id: str, *, active_only: bool = True) -> list[HealthGoal]:
        stmt = select(UserHealthGoal).where(UserHealthGoal.subject_id == subject_id)
        if active_only:
            stmt = stmt.where(UserHealthGoal.status == "active")
        stmt = stmt.order_by(UserHealthGoal.created_at.asc())
        rows = list(self.db.scalars(stmt))
        return [
            HealthGoal(
                id=row.id,
                subject_id=row.subject_id,
                goal_code=row.goal_code,
                label=row.label,
                status=row.status,
                created_at=row.created_at,
                source="user_goal",
                target_metrics=list(GOAL_METRICS.get(row.goal_code, ())),
            )
            for row in rows
        ]

    def replace_for_subject(self, subject_id: str, goal_codes: list[str]) -> list[HealthGoal]:
        codes = list(dict.fromkeys(code.strip() for code in goal_codes if code and code.strip()))
        unknown = [code for code in codes if code not in ALLOWED_GOAL_CODES]
        if unknown:
            raise ValidationAppError(f"Unsupported health goals: {', '.join(unknown)}")
        existing = list(
            self.db.scalars(select(UserHealthGoal).where(UserHealthGoal.subject_id == subject_id))
        )
        wanted = set(codes)
        for row in existing:
            if row.goal_code in wanted:
                row.status = "active"
                wanted.discard(row.goal_code)
            else:
                row.status = "paused"
        for code in codes:
            if code not in wanted:
                continue
            self.db.add(
                UserHealthGoal(
                    id=str(uuid4()),
                    subject_id=subject_id,
                    goal_code=code,
                    label=GOAL_LABELS[code],
                    status="active",
                )
            )
        self.db.commit()
        return self.list_for_subject(subject_id)

    def provided_facts(self, subject_id: str) -> list[ProvenancedFact]:
        rows = list(
            self.db.scalars(select(UserProfileFact).where(UserProfileFact.subject_id == subject_id))
        )
        return [
            ProvenancedFact(
                fact=row.fact_key,
                value=row.value,
                source="cura_user",
                fact_type=FactKind.user_provided_data,
                subject_id=subject_id,
                notes=[row.category],
            )
            for row in rows
        ]
