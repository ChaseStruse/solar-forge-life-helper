from pathlib import Path

import pytest

from solar_forge_desktop.paths import data_directory


def test_explicit_data_directory_requires_absolute_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SOLAR_FORGE_DESKTOP_DATA_DIR", str(tmp_path))
    assert data_directory() == tmp_path
    monkeypatch.setenv("SOLAR_FORGE_DESKTOP_DATA_DIR", "relative/path")
    with pytest.raises(ValueError, match="absolute path"):
        data_directory()
