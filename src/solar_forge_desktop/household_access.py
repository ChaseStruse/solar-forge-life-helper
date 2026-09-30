"""One service-level policy for private and household-visible records."""

from sqlalchemy import select

from solar_forge_desktop.storage import HouseholdMember, Profile

VISIBILITIES = ("private", "household")


def require_actor(session, actor_id: int) -> int:
    if session.get(Profile, actor_id) is None:
        raise ValueError("Profile not found.")
    household_id = session.scalar(select(HouseholdMember.household_id).where(
        HouseholdMember.profile_id == actor_id
    ))
    if household_id is None:
        raise ValueError("Profile is not in a household.")
    return household_id


def member_ids(session, actor_id: int) -> tuple[int, ...]:
    household_id = require_actor(session, actor_id)
    return tuple(session.scalars(select(HouseholdMember.profile_id).where(
        HouseholdMember.household_id == household_id
    )).all())


def can_read(session, actor_id: int, owner_id: int, visibility: str) -> bool:
    if actor_id == owner_id:
        return True
    return visibility == "household" and owner_id in member_ids(session, actor_id)


def require_visibility(value: str) -> str:
    if value not in VISIBILITIES:
        raise ValueError("Visibility must be Private or Household.")
    return value
