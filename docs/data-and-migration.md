# Data and migration

Solar Forge Life Helper stores account credentials, profile settings, and app records in a local SQLite database named `solar-forge-desktop.db`. Each account's records are kept separate within that database unless a task or calendar event is explicitly shared with the local household. Passwords are stored as salted scrypt hashes. The database, including journal entries and other personal records, is **not encrypted**.

## Where the database lives

| Launch method | Data location |
| --- | --- |
| Docker Compose | `/data/solar-forge-desktop.db` in the `solar-forge-life-helper-python-desktop` named volume by default. |
| Local Python | The operating system's per-user application data directory for Solar Forge Life Helper. |
| Local Python with `SOLAR_FORGE_DESKTOP_DATA_DIR` | The absolute directory specified by that variable. |

You can choose another Docker volume with `SOLAR_FORGE_DESKTOP_VOLUME_NAME`. Changing the volume or local data directory changes which database the app opens; it does not move data from the old location automatically.

On a new local installation, the first-run screen lets you choose the data and backup folders. The app stores those folder choices in `settings.json` under Qt's per-user application config directory, outside the database. At startup, `SOLAR_FORGE_DESKTOP_DATA_DIR` takes precedence over the saved data folder, which takes precedence over the operating system default. An environment override is meant for deliberate, often disposable runs; it does not replace the saved choice. A saved folder must still contain `solar-forge-desktop.db` on later launches, or the app asks you to locate the existing data.

Open **Settings** in the sidebar to see the active data folder and choose a separate backup folder. On a local installation, edit the data folder or use **Browse…**, select **Save**, then close and reopen the app. At the next launch, the app copies the SQLite database, checks the copy, and switches its saved location. It keeps the original database in the old folder for recovery. If the copy fails, the app continues to use the original location and shows an error. Only one app instance may run against a configuration at a time. **Back up now** creates a verified snapshot in the selected backup folder. **Verify latest** checks its checksum, SQLite integrity, and schema version. Optional daily or weekly backups run while the app is open, and retention removes only older verified copies after a new backup succeeds.

To restore, choose a file from **Restore from backup** in Settings, select **Restore…**, confirm, and restart. The app verifies the selected backup again before opening any pages, saves the current database to a `solar-forge-pre-restore-*.db` safety file and matching manifest, and opens the restored database. This safety copy appears in the restore list and is excluded from automatic retention. If reopening the restored database or saving the new setting fails, the app copies the safety file back. If rollback also fails, startup stops and shows the safety file path so the database is not silently replaced with an empty one. Settings warns when the latest regular backup is more than seven days old.

Docker Compose fixes the in-container data path at `/data`, so the data field is read only inside the container. To change its host location, stop the app and run `python scripts/configure_compose_storage.py --data /absolute/data/folder --backup /absolute/backup/folder`, then `docker compose up --build`. This creates an ignored `compose.override.yaml` with bind mounts. The prior named volume, or the prior chosen host folder, is mounted read only at `/previous-data`. If the new folder has no database, the app copies the old database with SQLite's backup API and verifies it before opening. The source is retained. If the target already has `solar-forge-desktop.db`, the app uses that existing database and does not overwrite it. Use the same `SOLAR_FORGE_DESKTOP_VOLUME_NAME` value if the prior volume used a custom name. To return to the default named volume, stop the app and remove `compose.override.yaml`; the original volume was not deleted.

Compose keeps preferences in a `/config` volume. Without an override, it offers a separate `/backups` volume as the default backup folder. These volumes survive `docker compose down`; `docker compose down -v` deletes them. If you browse for another backup folder inside Compose, it must be mounted into the container to persist. The host folders selected by the setup command must be writable by the Compose app user.

## Import an earlier Luna desktop database

The import runs only when the new `solar-forge-desktop.db` does not yet exist. It copies the old `luna-desktop.db` with SQLite's backup API, checks its integrity, and leaves the source untouched. On first launch the app checks, in order:

1. An old `luna-desktop.db` beside the new database, including inside an existing Docker volume.
2. The folder selected by `SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR`, if set.
3. For a local launch without `SOLAR_FORGE_DESKTOP_DATA_DIR`, the former Luna Life Helper application data directory.

Compose mounts the former host folder `~/.local/share/luna-life-helper-python-desktop` at `/legacy-data` by default. Set `SOLAR_FORGE_DESKTOP_LEGACY_DATA_DIR` to a different absolute host folder before `docker compose up` if your old file is elsewhere. The Docker container reads that folder without writing to it.

If your old data is in the former Docker volume, start Compose with `SOLAR_FORGE_DESKTOP_VOLUME_NAME=luna-life-helper-python-desktop`. The app will copy `luna-desktop.db` to the new filename inside that volume. Keep a separate backup before changing volumes or database files.

If the new database already exists, the app uses it and does not overwrite it with old data. Stop the app and inspect both locations before moving or replacing any database.

## Back up your data

Use **Back up now** in Settings to make a consistent copy without stopping the app. Each snapshot has a companion JSON manifest with its creation time, schema version, size, SHA-256 checksum, and app version. You can use **Verify latest** to check it again. Keep backups outside the repository and protect them as personal data; SQLite files are not encrypted. If the chosen folder syncs to a cloud service, that service may upload the backup. To make a manual file copy instead, stop the app first. For Compose, stop the container before copying files from its volume.

The app makes a snapshot before a supported schema upgrade. These upgrade snapshots are not a substitute for regular backups. `docker compose down` preserves the named volume; `docker compose down -v` removes it.

Schema version 15 adds a local household and owner/member memberships. Existing accounts join that household, but every existing task and calendar event is marked **private**. The migration saves a `pre-household-v14` snapshot before changing an older database. After migration, the owner can explicitly share a task or calendar event with the household. A member of a different household cannot see it. Shared task completion and shared calendar edits are available to members; deletion and visibility changes stay with the owner.

Schema version 16 adds opt-in calendar reminder rules and delivery records. The upgrade saves a `pre-reminders-v15` snapshot. It does not create reminders for existing events or change their times. Reminder notifications are not available in the UI yet.
