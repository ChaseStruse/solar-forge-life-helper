# Data and migration

Solar Forge Life Helper stores account credentials, profile settings, and app records in a local SQLite database named `solar-forge-desktop.db`. Each account's records are kept separate within that database. Passwords are stored as salted scrypt hashes. The database, including journal entries and other personal records, is **not encrypted**.

## Where the database lives

| Launch method | Data location |
| --- | --- |
| Docker Compose | `/data/solar-forge-desktop.db` in the `solar-forge-life-helper-python-desktop` named volume by default. |
| Local Python | The operating system's per-user application data directory for Solar Forge Life Helper. |
| Local Python with `SOLAR_FORGE_DESKTOP_DATA_DIR` | The absolute directory specified by that variable. |

You can choose another Docker volume with `SOLAR_FORGE_DESKTOP_VOLUME_NAME`. Changing the volume or local data directory changes which database the app opens; it does not move data from the old location automatically.

On a new local installation, the first-run screen lets you choose the data and future backup folders. The app stores those folder choices in `settings.json` under Qt's per-user application config directory, outside the database. At startup, `SOLAR_FORGE_DESKTOP_DATA_DIR` takes precedence over the saved data folder, which takes precedence over the operating system default. An environment override is meant for deliberate, often disposable runs; it does not replace the saved choice. A saved folder must still contain `solar-forge-desktop.db` on later launches, or the app asks you to locate the existing data.

Open **Settings** in the sidebar to see the active data folder and choose a separate backup folder. The data path is read only for now; a verified move flow is planned. Selecting a backup folder records your preference; automatic backups and restore are not yet available.

Docker Compose fixes the in-container data path at `/data`, so the folder picker cannot choose arbitrary host folders that have not been mounted. Compose keeps preferences in a `/config` volume and offers a separate `/backups` volume as the default backup folder. These volumes survive `docker compose down`; `docker compose down -v` deletes them. A host-side folder setup remains planned. If you browse for another backup folder inside Compose, it must be mounted into the container to persist.

## Import an earlier Luna desktop database

The import runs only when the new `solar-forge-desktop.db` does not yet exist. It copies the old `luna-desktop.db` with SQLite's backup API, checks its integrity, and leaves the source untouched. On first launch the app checks, in order:

1. An old `luna-desktop.db` beside the new database, including inside an existing Docker volume.
2. The folder selected by `SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR`, if set.
3. For a local launch without `SOLAR_FORGE_DESKTOP_DATA_DIR`, the former Luna Life Helper application data directory.

Compose mounts the former host folder `~/.local/share/luna-life-helper-python-desktop` at `/legacy-data` by default. Set `SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR` to a different absolute host folder before `docker compose up` if your old file is elsewhere. The Docker container reads that folder without writing to it.

If your old data is in the former Docker volume, start Compose with `SOLAR_FORGE_DESKTOP_VOLUME_NAME=luna-life-helper-python-desktop`. The app will copy `luna-desktop.db` to the new filename inside that volume. Keep a separate backup before changing volumes or database files.

If the new database already exists, the app uses it and does not overwrite it with old data. Stop the app and inspect both locations before moving or replacing any database.

## Back up your data

Stop the app before copying its database. For a local run, copy `solar-forge-desktop.db` from the chosen application data directory to a safe location. For Compose, stop the container with `docker compose down` and copy the same file from the named volume using Docker's volume tools. Keep backups outside the repository and protect them as personal data.

The app makes a snapshot before a supported schema upgrade. These upgrade snapshots are not a substitute for regular backups. `docker compose down` preserves the named volume; `docker compose down -v` removes it.
