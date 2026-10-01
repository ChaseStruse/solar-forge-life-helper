# Solar Forge Life Helper desktop (Python)

See the [application documentation](docs/README.md) for setup, feature guides, data migration, and development notes.

This is a source-run Python/PySide6 application. It opens with local sign-up or login,
then shows a Dashboard with working Easy Budget, Task List, Easy Journal,
Medicine Tracker, Habit Tracker, Calorie Tracker, Weight Tracker, Workout Tracker,
Pet Care, Meal Planner, Home Maintenance, and Calendar cards and sidebar navigation.
The avatar button opens Solar Forge Profile for editing the display name, bio, and avatar.
Dashboard app cards reflow from one column on a narrow window to four at 1280px,
five at 1600px, and six at 1920px.
Easy Budget supports monthly income, expenses, recurrence, filtering, sorting and CSV
export with exact-cent SQLite storage. Easy Journal supports private entry creation,
editing, deletion, and a newest-first timeline. Medicine Tracker records doses for
people and pets with their next scheduled times and opt-in next-dose reminders.
Habit Tracker records daily yes/no
checks in a weekly grid. Calorie Tracker has daily goals, food logs, and progress
for the selected date. Weight Tracker has goals, daily weigh-ins, and an offline
trend chart. Workout Tracker logs daily exercises with sets, reps, bodyweight or
optional pounds, notes, and inline editing. Pet Care keeps profiles and dated
care records for each animal, with matching Medicine Tracker history. Meal Planner
organizes dinners by week and builds a grocery list from reusable favorites. Home
Maintenance tracks recurring household care and due dates. Calendar plans timed
and all-day events with month/week views, recurring series, and opt-in reminders
for timed events while signed in. The
Dashboard shows only migrated apps;
summary widgets will appear as their data modules are implemented. The first account
claims an existing sole Home profile and its tasks. Additional accounts have separate
task lists, budgets, journals, medicine logs, habits, calorie entries, weight,
workout logs, pet records, meal plans, maintenance items, calendar events, and profile settings. Sign out returns
to login, and each
launch asks for a password. Passwords
are stored as salted scrypt hashes in the local SQLite database; the database and its
pre-upgrade snapshot are not encrypted.

## Run in Docker on Linux Wayland

From this directory, in a Linux Wayland session with Docker Compose available:

```bash
docker compose up --build
```

Compose builds the Python 3.14 image and displays the Qt window through the current
Wayland session. Tasks, budgets, journals, medicine logs, habits, calorie entries,
weight records, workout logs, pet records, meal plans, maintenance items, calendar events,
and profile settings persist in the Docker data volume
`solar-forge-life-helper-python-desktop`. Storage preferences and the backup folder
have separate persistent Compose volumes. `docker compose down` keeps all three volumes;
`docker compose down -v` deletes them. The container has no network access. Press Ctrl+C to stop it, or
run `docker compose down`.

Compose mounts `src` read only, so a normal `docker compose down` followed by
`docker compose up` uses the current Python application source even when an older image
already exists. Use `docker compose up --build` after changes to dependencies or the
Dockerfile. Existing version 1 through 13 desktop databases are upgraded in place only after
SQLite snapshots are saved; the first account claims its Home tasks.

On first launch, an existing Python desktop database in the previous default host data
folder is copied into the Docker volume with SQLite's backup API. The original file is
mounted read only and remains in place. By default, Compose looks in the former
`luna-life-helper-python-desktop` host data folder for `luna-desktop.db`. To select
a different legacy folder for this one-time copy, set
`SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR` to its absolute path.
If your existing data is in the former Docker volume, set
`SOLAR_FORGE_DESKTOP_VOLUME_NAME=luna-life-helper-python-desktop` when starting Compose.
The app copies its old database file within that volume on first launch.

To use a different persistent volume name, set it before starting:

```bash
SOLAR_FORGE_DESKTOP_VOLUME_NAME=my-solar-forge-data docker compose up --build
```

To store the standard Compose database in a host folder instead, stop the app and run:

```bash
python scripts/configure_compose_storage.py --data /absolute/path/to/family-data --backup /absolute/path/to/family-backups
docker compose up --build
```

The command writes a local, ignored `compose.override.yaml`. On first start with an empty
chosen data folder, the app copies the database from the previous Compose data location
using SQLite's backup API and leaves the original in place. Run the command again to
choose another host folder. Use **Back up now** in Settings to write to that backup folder;
scheduled backups can run while the app is open. Keep the same `SOLAR_FORGE_DESKTOP_VOLUME_NAME` if you
previously customized it. The folders must be writable by the Compose app user.

The volume is initialized with the app user's permissions. On Linux installations where
the current user's numeric ID is not 1000, set `SOLAR_FORGE_DESKTOP_UID` and
`SOLAR_FORGE_DESKTOP_GID` to the values from `id -u` and `id -g` before building.

The launcher needs a Linux Wayland session and access to Docker. It does not currently
forward an X11 display or a Windows desktop. On those systems, use the source commands
below while their Docker display paths remain open work.

## Run from local Python

Use Python 3.14 and [uv](https://docs.astral.sh/uv/). From the repository root on Linux:

```bash
uv sync --frozen
uv run --frozen solar-forge-desktop
```

On Windows PowerShell:

```powershell
uv sync --frozen
uv run --frozen solar-forge-desktop
```

The app writes to the operating system's per-user application data directory so tasks
persist between launches. A new local installation asks you to choose the data folder
and a separate backup folder. Open **Settings** in the sidebar to edit those folders,
select **Back up now**, and verify the latest backup. You can also enable daily or weekly
backups and choose how many to keep. Scheduled backups run while the app is open. To restore,
choose a listed backup in Settings and restart the app; the current database is saved for
recovery first. On a local
installation, changing the data folder copies and verifies the database on the next
launch and retains the original. On first native launch,
it copies an existing database from
the former Luna Life Helper app data directory into the new location. For an isolated
test run, set `SOLAR_FORGE_DESKTOP_DATA_DIR` to a new, empty **absolute** directory
before launch. For example, on Linux use
`SOLAR_FORGE_DESKTOP_DATA_DIR="$(mktemp -d)" uv run --frozen solar-forge-desktop`; on PowerShell use
`$env:SOLAR_FORGE_DESKTOP_DATA_DIR = Join-Path $env:TEMP ("solar-forge-desktop-" + [guid]::NewGuid())`
before the run command. Never point it at the web application's `db/app.db` or a
previous desktop prototype database.

Container checks from the repository root:

```bash
docker build -t solar-forge-desktop-test -f Dockerfile.test .
docker run --rm solar-forge-desktop-test
```

The Docker run uses Python 3.14 and Qt's offscreen platform for tests.
To run the same tests locally, use
`QT_QPA_PLATFORM=offscreen uv run --frozen --extra test pytest -q`.
