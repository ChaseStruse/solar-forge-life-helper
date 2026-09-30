"""Source-run Linux Qt/SQLite smoke check using a disposable data directory."""

import os
import sys
import time

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from solar_forge_desktop.paths import data_directory
from solar_forge_desktop.storage import Storage
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.window import TaskWindow


def main() -> int:
    if not os.environ.get("SOLAR_FORGE_DESKTOP_DATA_DIR"):
        raise RuntimeError("Set SOLAR_FORGE_DESKTOP_DATA_DIR to a disposable absolute directory.")
    app = QApplication(sys.argv)
    app.setOrganizationName("Solar Forge Life Helper")
    app.setApplicationName("Solar Forge Life Helper")
    storage = Storage(data_directory() / "solar-forge-desktop.db")
    profile_id = storage.default_profile_id()
    service = TaskService(storage)
    window = TaskWindow(service, profile_id, storage.close)
    window.show()
    started = time.monotonic()
    outcome = {"code": 1}

    def add_task() -> None:
        window.title_input.setText("Native smoke task")
        window.add_task()
        QTimer.singleShot(100, verify)

    def verify() -> None:
        if [task.title for task in service.list_tasks(profile_id)[0]] == ["Native smoke task"]:
            outcome["code"] = 0
            window.close()
            app.quit()
        elif time.monotonic() - started > 5:
            print(f"Native task save failed: {window.status.text()}", file=sys.stderr)
            window.close()
            app.quit()
        else:
            QTimer.singleShot(100, verify)

    QTimer.singleShot(150, add_task)
    app.exec()
    return outcome["code"]


if __name__ == "__main__":
    raise SystemExit(main())
