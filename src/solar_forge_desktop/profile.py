"""Profile-scoped personal details and saved presentation preferences."""

import re
from dataclasses import dataclass

from sqlalchemy import select

from solar_forge_desktop.storage import Profile, ProfileSettings, Storage

AVATAR_COLORS = (
    ("#8b5cf6", "Purple"), ("#ec4899", "Pink"), ("#6366f1", "Indigo"),
    ("#10b981", "Green"), ("#06b6d4", "Blue"), ("#f59e0b", "Orange"),
)
AVATAR_ICONS = (
    ("🌙", "Moon"), ("🚀", "Rocket"), ("🌸", "Flower"),
    ("⚡", "Spark"), ("🎯", "Target"), ("🧠", "Brain"),
)


@dataclass(frozen=True)
class ProfileView:
    name: str
    username: str | None
    bio: str
    avatar_color: str
    avatar_emoji: str
    favorite_apps: tuple[str, ...]
    visible_widgets: tuple[str, ...]
    highlight_order: tuple[str, ...]
    quick_access_apps: tuple[str, ...]


def _items(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


class ProfileService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def view(self, profile_id: int) -> ProfileView:
        with self.storage.sessions() as session:
            profile = session.get(Profile, profile_id)
            if profile is None:
                raise ValueError("Profile not found.")
            settings = session.scalar(select(ProfileSettings).where(
                ProfileSettings.profile_id == profile_id))
            if settings is None:
                return ProfileView(profile.name, profile.username, "Solar Forge Life Helper member",
                                   "#8b5cf6", "🌙", ("budget", "calorie", "weight", "journal"),
                                   ("journal", "weight", "calorie"),
                                   ("budget", "calorie", "weight", "journal"),
                                   ("budget", "calorie", "weight", "journal", "workout", "tasks",
                                    "calendar", "habits", "medicine", "pets", "maintenance",
                                    "meals"))
            return ProfileView(profile.name, profile.username, settings.bio,
                               settings.avatar_color, settings.avatar_emoji,
                               _items(settings.favorite_apps), _items(settings.visible_widgets),
                               _items(settings.highlight_order),
                               _items(settings.quick_access_apps))

    def update(self, profile_id: int, name: str, bio: str,
               avatar_color: str, avatar_emoji: str) -> ProfileView:
        name = name.strip() if isinstance(name, str) else ""
        bio = bio.strip() if isinstance(bio, str) else ""
        if not name:
            raise ValueError("Name cannot be empty.")
        if len(name) > 100:
            raise ValueError("Display name must be 100 characters or fewer.")
        if len(bio) > 2000:
            raise ValueError("Bio must be 2000 characters or fewer.")
        if not isinstance(avatar_color, str) or not re.fullmatch(
            r"#[0-9A-Fa-f]{6}", avatar_color
        ):
            avatar_color = "#8b5cf6"
        if not isinstance(avatar_emoji, str) or len(avatar_emoji) > 2 or not avatar_emoji:
            avatar_emoji = "🌙"
        with self.storage.sessions.begin() as session:
            profile = session.get(Profile, profile_id)
            if profile is None:
                raise ValueError("Profile not found.")
            settings = session.scalar(select(ProfileSettings).where(
                ProfileSettings.profile_id == profile_id))
            if settings is None:
                settings = ProfileSettings(profile_id=profile_id)
                session.add(settings)
            profile.name = name
            settings.bio = bio
            settings.avatar_color = avatar_color
            settings.avatar_emoji = avatar_emoji
        return self.view(profile_id)
