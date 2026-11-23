"""Loads the signed in member's own data and returns the guided story. The principal decides whose data is read."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.auth.models import AuthenticatedPrincipal
from app.biomarkers.health_categories import category
from app.health_explanation.story_builder import build_story
from app.health_explanation.story_llm import narrate
from app.health_explanation.story_schema import HealthStory
from app.health_explanation.user_context import load_lifestyle
from app.pipeline.unified_service import _load
from app.providers.registry import ProviderRegistry

logger = logging.getLogger("cura.story")


def category_story(principal: AuthenticatedPrincipal, registry: ProviderRegistry, category_id: str, db: Session | None = None, language: str = "en") -> HealthStory | None:
    if category(category_id) is None:
        return None
    blood, bio = _load(principal, registry)
    lifestyle = load_lifestyle(principal, registry, db)
    story = build_story(category_id, blood, bio, lifestyle)
    if story is None:
        return None
    return narrate(principal.subject_id, story, language)
