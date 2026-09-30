# Development

The desktop app is a Python 3.14/PySide6 project managed with uv. `pyproject.toml` defines the `solar-forge-desktop` launcher; `uv.lock` pins its dependencies.

## Project layout

| Path | Purpose |
| --- | --- |
| `src/solar_forge_desktop/__main__.py` | Starts Qt, locates or imports the database, and switches between sign-in and the workspace. |
| `src/solar_forge_desktop/window.py` | Main window, dashboard, sidebar, themes, and Task List page. |
| `src/solar_forge_desktop/*_page.py` | Views and interactions for the other modules. |
| `src/solar_forge_desktop/*.py` | Services and application logic for each module. |
| `src/solar_forge_desktop/storage.py` | SQLAlchemy models, schema upgrades, and database import. |
| `tests/` | Service, storage, and Qt page tests. |
| `compose.yaml`, `Dockerfile.run`, `Dockerfile.test` | Wayland launcher and containerized test setup. |

The pages call services with the signed-in profile ID. Services read and write through `Storage`. A background worker keeps many page operations off the Qt UI thread. Database schema upgrades are keyed by SQLite `PRAGMA user_version`; add a migration when changing persisted tables.

## Run checks

With Python 3.14 and uv installed:

```bash
uv sync --frozen --extra test
QT_QPA_PLATFORM=offscreen uv run --frozen --extra test pytest -q
uv run --frozen --extra test ruff check src tests
```

To run the test suite in Docker:

```bash
docker build -t solar-forge-desktop-test -f Dockerfile.test .
docker run --rm solar-forge-desktop-test
```

For visual checks on Linux Wayland, use `docker compose up --build` and inspect the running app. Stop it with Ctrl+C or `docker compose down`; do not add `-v` unless you intend to delete its data volume. Use a disposable data directory or volume for checks that create records.

## Adding a module

Add the storage model and migration, then the service, page, dashboard card, and sidebar action. Keep data scoped to the active profile. Add tests for behavior that could lose or mix account data, and verify the page at the supported window sizes.
