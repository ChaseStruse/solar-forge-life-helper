"""Host folder choices retain a previous mount for one-time migration."""

import importlib.util
import json
from pathlib import Path

import pytest

from solar_forge_desktop.bootstrap import import_previous_database
from solar_forge_desktop.configuration import DATABASE_NAME
from solar_forge_desktop.storage import Storage

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "configure_compose_storage.py"
SPEC = importlib.util.spec_from_file_location("configure_compose_storage", SCRIPT)
assert SPEC and SPEC.loader
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


def test_compose_override_tracks_previous_data_folder(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.setattr(setup, "ROOT", project)
    monkeypatch.setattr(setup, "OVERRIDE", project / "compose.override.yaml")
    first = tmp_path / "first"
    backup = tmp_path / "backup"

    setup.configure(str(first), str(backup))
    initial = json.loads(setup.OVERRIDE.read_text())
    mounts = initial["services"]["desktop"]["volumes"]
    assert mounts[0]["source"] == str(first)
    assert mounts[2]["source"] == "solar_forge_desktop_data"

    second = tmp_path / "second"
    setup.configure(str(second), str(backup))
    updated = json.loads(setup.OVERRIDE.read_text())
    mounts = updated["services"]["desktop"]["volumes"]
    assert mounts[0]["source"] == str(second)
    assert mounts[2]["source"] == str(first)
    assert mounts[2]["read_only"] is True


def test_unknown_compose_override_is_preserved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    override = tmp_path / "compose.override.yaml"
    override.write_text("services: {}\n")
    monkeypatch.setattr(setup, "OVERRIDE", override)

    with pytest.raises(ValueError, match="not generated"):
        setup.configure(str(tmp_path.parent / "data"), str(tmp_path.parent / "backup"))
    assert override.read_text() == "services: {}\n"


def test_compose_migration_copies_old_database_once(tmp_path: Path) -> None:
    old = tmp_path / "old"
    storage = Storage(old / DATABASE_NAME)
    profile_id = storage.create_profile("Household")
    storage.close()
    original = (old / DATABASE_NAME).read_bytes()
    new = tmp_path / "new" / DATABASE_NAME

    import_previous_database(new, {"SOLAR_FORGE_DESKTOP_PREVIOUS_DATA_DIR": str(old)})

    moved = Storage(new)
    assert moved.profile_name(profile_id) == "Household"
    moved.close()
    assert (old / DATABASE_NAME).read_bytes() == original
