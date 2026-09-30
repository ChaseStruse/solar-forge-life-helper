# Getting started

Run commands from the repository root.

## Docker on Linux Wayland

You need Docker with Compose and an active Wayland session. Start the app with:

```bash
docker compose up --build
```

The desktop window opens on your current display. Press Ctrl+C to stop it, or run `docker compose down` from another terminal. Compose keeps the database in the `solar-forge-life-helper-python-desktop` volume. Do not use `docker compose down -v` unless you intend to delete that volume and its data.

If your Linux user ID or group ID is not 1000, set `SOLAR_FORGE_DESKTOP_UID` and `SOLAR_FORGE_DESKTOP_GID` to the values from `id -u` and `id -g` before building. The Compose launcher currently supports Wayland; it does not forward X11 or a Windows desktop.

## Local Python

Install Python 3.14 and [uv](https://docs.astral.sh/uv/). On Linux or Windows, run:

```bash
uv sync --frozen
uv run --frozen solar-forge-desktop
```

The local launcher stores data in the operating system's per-user application data directory. To choose a different location, set `SOLAR_FORGE_DESKTOP_DATA_DIR` to an **absolute** path before launching. See [Data and migration](data-and-migration.md) for the database name and the old-app import behavior.

## First account

On a new database, choose **Create account**. Usernames are 3–80 characters and may contain lowercase letters, digits, dots, hyphens, and underscores. The app converts uppercase letters to lowercase. Passwords must have at least 8 characters.

The first account claims an existing unclaimed Home profile if the database has one. Later accounts have separate records. Each launch asks you to sign in, and **Sign out** returns to the sign-in screen.

After signing in, use the sidebar or dashboard cards to open a module. The avatar button opens **Solar Forge Profile**, where you can edit your display name, bio, and avatar.
