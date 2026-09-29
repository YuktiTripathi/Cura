from app.auth.models import AuthenticatedPrincipal
from app.contracts.user import UserProfile
from integrations.mock.loader import load_json


class MockUserProvider:
    def __init__(self) -> None:
        self._rows = load_json("users.json")

    def get_profile(self, principal: AuthenticatedPrincipal) -> UserProfile:
        for row in self._rows:
            if row["subject_id"] == principal.subject_id:
                profile = UserProfile.model_validate(row)
                first = profile.first_name or (profile.display_name or "").strip() or None
                return profile.model_copy(update={"first_name": first, "display_name": first or ""})
        return UserProfile(subject_id=principal.subject_id, display_name="", first_name=None, last_name=None)

    def available_topics(self, principal: AuthenticatedPrincipal) -> list[str]:
        return ["vitamin_d", "cardiac_health", "nafld"]
