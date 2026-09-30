# Getting started

Run commands from the repository root.

## Docker on Linux Wayland

You need Docker with Compose and an active Wayland session. Start the app with:

```bash
docker compose up --build
```

The desktop window opens on your current display. Press Ctrl+C to stop it, or run `docker compose down` from another terminal. Compose keeps the database in the `solar-forge-life-helper-python-desktop` volume. Do not use `docker compose down -v` unless you intend to delete that volume and its data.

To choose host folders for Compose data and future backups, stop the app and run `python scripts/configure_compose_storage.py --data /absolute/data/folder --backup /absolute/backup/folder`. Then start with `docker compose up --build`. The app copies an existing database from the previous Compose location into an empty selected data folder and keeps the source. See [Data and migration](data-and-migration.md) before switching an existing installation.

If your Linux user ID or group ID is not 1000, set `SOLAR_FORGE_DESKTOP_UID` and `SOLAR_FORGE_DESKTOP_GID` to the values from `id -u` and `id -g` before building. The Compose launcher currently supports Wayland; it does not forward X11 or a Windows desktop.

## Local Python

Install Python 3.14 and [uv](https://docs.astral.sh/uv/). On Linux or Windows, run:

```bash
uv sync --frozen
uv run --frozen solar-forge-desktop
```

The local launcher stores data in the operating system's per-user application data directory. To choose a different location, set `SOLAR_FORGE_DESKTOP_DATA_DIR` to an **absolute** path before launching. See [Data and migration](data-and-migration.md) for the database name and the old-app import behavior.

On a new local installation, the app first asks you to choose a data folder and a separate folder for future backups. The suggested folders are ready to use. The backup choice is saved, but automatic backups are still being built. Existing installations continue using their current database. If a saved data folder later goes missing, the app asks you to reconnect it or locate the existing database instead of starting with an empty one.

## First account

After choosing storage on a new installation, select **Create account**. Usernames are 3–80 characters and may contain lowercase letters, digits, dots, hyphens, and underscores. The app converts uppercase letters to lowercase. Passwords must have at least 8 characters.

The first account claims an existing unclaimed Home profile if the database has one. Later accounts have separate records. Each launch asks you to sign in, and **Sign out** returns to the sign-in screen.

After signing in, use the sidebar or dashboard cards to open a module. The avatar button opens **Solar Forge Profile**, where you can edit your display name, bio, and avatar.
