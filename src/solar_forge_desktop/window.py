"""Solar Forge's native dashboard and app pages."""

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCalendarWidget,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.backup_scheduler import BackupScheduler
from solar_forge_desktop.budget import BudgetService
from solar_forge_desktop.budget_page import STYLE as BUDGET_STYLE
from solar_forge_desktop.budget_page import BudgetPage
from solar_forge_desktop.calendar import CalendarService
from solar_forge_desktop.calendar_page import STYLE as CALENDAR_STYLE
from solar_forge_desktop.calendar_page import CalendarPage
from solar_forge_desktop.calendar_widgets import SELECTOR_STYLE, style_calendar
from solar_forge_desktop.calorie import CalorieService
from solar_forge_desktop.calorie_page import STYLE as CALORIE_STYLE
from solar_forge_desktop.calorie_page import CaloriePage
from solar_forge_desktop.configuration import SettingsStore
from solar_forge_desktop.habit_page import STYLE as HABIT_STYLE
from solar_forge_desktop.habit_page import HabitPage
from solar_forge_desktop.habits import HabitService
from solar_forge_desktop.journal import JournalService
from solar_forge_desktop.journal_page import STYLE as JOURNAL_STYLE
from solar_forge_desktop.journal_page import JournalPage
from solar_forge_desktop.maintenance import MaintenanceService
from solar_forge_desktop.maintenance_page import STYLE as MAINTENANCE_STYLE
from solar_forge_desktop.maintenance_page import MaintenancePage
from solar_forge_desktop.meal_page import STYLE as MEAL_STYLE
from solar_forge_desktop.meal_page import MealPage
from solar_forge_desktop.meals import MealService
from solar_forge_desktop.medicine import MedicineService
from solar_forge_desktop.medicine_page import STYLE as MEDICINE_STYLE
from solar_forge_desktop.medicine_page import MedicinePage
from solar_forge_desktop.pet_page import STYLE as PET_STYLE
from solar_forge_desktop.pet_page import PetPage
from solar_forge_desktop.pets import PetService
from solar_forge_desktop.profile import ProfileService, ProfileView
from solar_forge_desktop.profile_page import STYLE as PROFILE_STYLE
from solar_forge_desktop.profile_page import ProfilePage
from solar_forge_desktop.settings_dialog import StorageSettingsDialog
from solar_forge_desktop.storage import TaskItem
from solar_forge_desktop.tasks import TaskService
from solar_forge_desktop.weight import WeightService
from solar_forge_desktop.weight_page import STYLE as WEIGHT_STYLE
from solar_forge_desktop.weight_page import WeightPage
from solar_forge_desktop.workers import BackgroundWorker
from solar_forge_desktop.workout import WorkoutService
from solar_forge_desktop.workout_page import STYLE as WORKOUT_STYLE
from solar_forge_desktop.workout_page import WorkoutPage

STYLE = """
QMainWindow, QWidget#root { background: #0a0712; color: #f3f4f6; }
QFrame#sidebar { background: #120e24; border-right: 1px solid #292339; }
QFrame#card { background: #1a1533; border: 1px solid #302943; border-radius: 16px; }
QFrame#taskRow { background: #201a38; border: 1px solid #302943; border-radius: 10px; }
QLabel#brandIcon { background: #8b5cf6; color: white; border-radius: 12px;
                   font-size: 23px; font-weight: 700; }
QLabel#brand { color: #d6b4ff; font-size: 17px; font-weight: 800; }
QLabel#heading { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#section { color: #f3f4f6; font-size: 18px; font-weight: 700; }
QLabel#muted { color: #a1a1aa; }
QLabel#navLabel { color: #71717a; font-size: 11px; font-weight: 700; }
QLabel#taskTitleText { color: #f3f4f6; font-size: 14px; }
QLabel#completedTitle { color: #a1a1aa; text-decoration: line-through; }
QLabel#completionTime { color: #71717a; font-size: 11px; }
QLabel#eyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#sectionMeta { color: #71717a; font-size: 13px; }
QLabel#appIcon { background: #33234e; color: #f3f4f6; border-radius: 9px;
                 font-size: 17px; font-weight: 700; }
QLabel#appTitle { color: #f3f4f6; font-size: 15px; font-weight: 700; }
QLabel#appDescription { color: #71717a; font-size: 12px; }
QLabel#appArrow { color: #ec4899; font-size: 20px; }
QLabel#error { color: #fb7185; }
QFrame#topbar { background: #0a0712; border: none; }
QLineEdit#appSearch { background: #151027; border: 1px solid #292339;
    border-radius: 23px; padding: 10px 18px; font-size: 14px; }
QPushButton#themeButton { background: #151027; border: 1px solid #292339;
    border-radius: 22px; padding: 10px 15px; font-weight: 700; }
QPushButton#profileButton { background: #8b5cf6; color: #facc15;
    border: 2px solid #a855f7; border-radius: 22px; padding: 0;
    font-size: 26px; }
QLineEdit { background: #211b39; color: #f3f4f6; border: 1px solid #39314e;
            border-radius: 10px; padding: 11px 15px; }
QLineEdit:focus { border-color: #8b5cf6; }
QComboBox#taskVisibility { background: #211b39; color: #f3f4f6;
    border: 1px solid #39314e; border-radius: 9px; padding: 8px 12px; }
QComboBox#taskVisibility QAbstractItemView { background: #211b39; color: #f3f4f6; }
QPushButton { background: #292143; color: #f3f4f6; border: 1px solid #483a64;
              border-radius: 10px; padding: 10px 15px; }
QPushButton:hover { background: #3d315d; }
QPushButton#primary { background: #8b5cf6; border-color: #a56eff; font-weight: 700; }
QPushButton#primary:hover { background: #a06df9; }
QPushButton#nav { background: #302348; border-color: #674394; text-align: left; }
QPushButton#nav:!checked { background: transparent; border-color: transparent;
                           color: #a1a1aa; }
QPushButton#appCard { background: #1a1533; border: 1px solid #302943;
                      border-radius: 16px; text-align: left; padding: 0; }
QPushButton#appCard:hover { border-color: #674394; background: #241e45; }
QPushButton[role="delete"] { background: #3a1d39; border-color: #5b3048; color: #fb7185; }
QPushButton[role="delete"]:hover { background: #512340; }
QCheckBox { color: #f3f4f6; spacing: 10px; }
QCheckBox::indicator { width: 20px; height: 20px; border: 2px solid #8b5cf6;
                       border-radius: 5px; background: #211b39; }
QCheckBox::indicator:hover { border-color: #c4b5fd; }
QCheckBox::indicator:checked { border: none; background: transparent;
                               image: url("__CHECK_ICON__"); }
QScrollArea, QScrollArea QWidget, QWidget#taskListContainer {
    border: none; background: transparent; }
""" + SELECTOR_STYLE

THEMES = {
    "Solar Forge Glow": {},
    "Cyberpunk": {
        "#0a0712": "#10061a", "#120e24": "#180822", "#151027": "#250c36",
        "#1a1533": "#250c36", "#211b30": "#39114c", "#211b39": "#39114c",
        "#302943": "#512d63", "#292339": "#512d63", "#8b5cf6": "#00f5d4",
        "#ec4899": "#ff3cac", "#f3f4f6": "#fff7ff", "#a1a1aa": "#d7c5df",
        "#71717a": "#9d88aa",
    },
    "Ocean Blue": {
        "#0a0712": "#06172c", "#120e24": "#0a2340", "#151027": "#0e2f52",
        "#1a1533": "#0e2f52", "#211b30": "#133e68", "#211b39": "#133e68",
        "#302943": "#315f7e", "#292339": "#315f7e", "#8b5cf6": "#38bdf8",
        "#ec4899": "#22d3ee", "#f3f4f6": "#effaff", "#a1a1aa": "#b5d4e9",
        "#71717a": "#79a6c1",
    },
    "Aurora": {
        "#0a0712": "#071b1c", "#120e24": "#0b2928", "#151027": "#113936",
        "#1a1533": "#113936", "#211b30": "#184d48", "#211b39": "#184d48",
        "#302943": "#316c60", "#292339": "#316c60", "#8b5cf6": "#34d399",
        "#ec4899": "#a78bfa", "#f3f4f6": "#effdf7", "#a1a1aa": "#b7ddd2",
        "#71717a": "#82aaa0",
    },
}


def _themed_style(style: str, theme: str) -> str:
    palette = THEMES[theme]
    return re.sub(r"#[0-9a-fA-F]{6}\b", lambda match: palette.get(
        match.group(0).lower(), match.group(0)
    ), style)


class DeleteTaskDialog(QDialog):
    """A confirmation that uses the same Solar Forge colors as the task view."""

    def __init__(self, task_title: str, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("deleteTaskDialog")
        self.setWindowTitle("Delete task")
        self.setMinimumWidth(360)
        self.setStyleSheet("""
            QDialog#deleteTaskDialog { background: #1a1533; border: 1px solid #493763; }
            QLabel#deleteHeading { color: #f3f4f6; font-size: 18px; font-weight: 700; }
            QLabel#deleteMessage { color: #a1a1aa; font-size: 14px; }
            QPushButton#cancelDelete { background: #292143; color: #f3f4f6;
                border: 1px solid #483a64; border-radius: 10px; padding: 10px 18px; }
            QPushButton#cancelDelete:hover { background: #3d315d; }
            QPushButton#confirmDelete { background: #be3153; color: #fff;
                border: 1px solid #e44970; border-radius: 10px; padding: 10px 18px;
                font-weight: 700; }
            QPushButton#confirmDelete:hover { background: #d94367; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        heading = QLabel("Delete task?")
        heading.setObjectName("deleteHeading")
        layout.addWidget(heading)
        message = QLabel(f"Delete '{task_title}'? This can't be undone.")
        message.setObjectName("deleteMessage")
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setWordWrap(True)
        layout.addWidget(message)
        actions = QHBoxLayout()
        actions.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("cancelDelete")
        cancel.clicked.connect(self.reject)
        cancel.setDefault(True)
        actions.addWidget(cancel)
        confirm = QPushButton("Delete task")
        confirm.setObjectName("confirmDelete")
        confirm.clicked.connect(self.accept)
        actions.addWidget(confirm)
        layout.addLayout(actions)
        cancel.setFocus()


class TaskWindow(QMainWindow):
    def __init__(
        self, service: TaskService, profile_id: int, on_close: Callable[[], None],
        profile_name: str = "Home", on_sign_out: Callable[[], None] | None = None,
        settings_store: SettingsStore | None = None, data_directory: Path | None = None,
        backup_scheduler: BackupScheduler | None = None,
    ):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.profile_name = profile_name
        self.on_close = on_close
        self.on_sign_out = on_sign_out
        self.settings_store = settings_store
        self.data_directory = data_directory
        self.backup_scheduler = backup_scheduler
        self.setWindowTitle("Solar Forge Life Helper — Dashboard")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "solar-forge.svg")))
        self.resize(1280, 800)
        self.setMinimumSize(690, 500)
        check_icon = (Path(__file__).parent / "assets" / "task-checked.svg").as_posix()
        self.setStyleSheet(STYLE.replace("__CHECK_ICON__", check_icon))
        self._build()
        self._set_profile_avatar(ProfileService(self.service.storage).view(self.profile_id))
        self._worker = BackgroundWorker(self, "solar-forge-tasks")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)
        self.show_dashboard()

    def _build(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(280)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(24, 32, 24, 24)
        nav.setSpacing(12)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_icon = QLabel("◉")
        brand_icon.setObjectName("brandIcon")
        brand_icon.setFixedSize(40, 40)
        brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_row.addWidget(brand_icon)
        brand = QLabel("Solar Forge\nLife Helper")
        brand.setObjectName("brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        brand_row.addWidget(brand)
        brand_row.addStretch()
        nav.addLayout(brand_row)
        nav.addSpacing(35)
        label = QLabel("QUICK ACCESS")
        label.setObjectName("navLabel")
        nav.addWidget(label)
        self.dashboard_nav = QPushButton("▦   Dashboard")
        self.dashboard_nav.setObjectName("nav")
        self.dashboard_nav.setAccessibleName("Dashboard")
        self.dashboard_nav.setCheckable(True)
        self.dashboard_nav.clicked.connect(self.show_dashboard)
        nav.addWidget(self.dashboard_nav)
        self.budget_nav = QPushButton("◫   Easy Budget")
        self.budget_nav.setObjectName("nav")
        self.budget_nav.setAccessibleName("Easy Budget")
        self.budget_nav.setCheckable(True)
        self.budget_nav.clicked.connect(self.show_budget)
        nav.addWidget(self.budget_nav)
        self.tasks_nav = QPushButton("☑   Task List")
        self.tasks_nav.setObjectName("nav")
        self.tasks_nav.setAccessibleName("Task List")
        self.tasks_nav.setCheckable(True)
        self.tasks_nav.clicked.connect(self.show_tasks)
        nav.addWidget(self.tasks_nav)
        self.journal_nav = QPushButton("✎   Easy Journal")
        self.journal_nav.setObjectName("nav")
        self.journal_nav.setAccessibleName("Easy Journal")
        self.journal_nav.setCheckable(True)
        self.journal_nav.clicked.connect(self.show_journal)
        nav.addWidget(self.journal_nav)
        self.medicine_nav = QPushButton("✚   Medicine Tracker")
        self.medicine_nav.setObjectName("nav")
        self.medicine_nav.setAccessibleName("Medicine Tracker")
        self.medicine_nav.setCheckable(True)
        self.medicine_nav.clicked.connect(self.show_medicine)
        nav.addWidget(self.medicine_nav)
        self.habit_nav = QPushButton("✓   Habit Tracker")
        self.habit_nav.setObjectName("nav")
        self.habit_nav.setAccessibleName("Habit Tracker")
        self.habit_nav.setCheckable(True)
        self.habit_nav.clicked.connect(self.show_habits)
        nav.addWidget(self.habit_nav)
        self.calorie_nav = QPushButton("◉   Calorie Tracker")
        self.calorie_nav.setObjectName("nav")
        self.calorie_nav.setAccessibleName("Calorie Tracker")
        self.calorie_nav.setCheckable(True)
        self.calorie_nav.clicked.connect(self.show_calorie)
        nav.addWidget(self.calorie_nav)
        self.weight_nav = QPushButton("◉   Weight Tracker")
        self.weight_nav.setObjectName("nav")
        self.weight_nav.setAccessibleName("Weight Tracker")
        self.weight_nav.setCheckable(True)
        self.weight_nav.clicked.connect(self.show_weight)
        nav.addWidget(self.weight_nav)
        self.workout_nav = QPushButton("◉   Workout Tracker")
        self.workout_nav.setObjectName("nav")
        self.workout_nav.setAccessibleName("Workout Tracker")
        self.workout_nav.setCheckable(True)
        self.workout_nav.clicked.connect(self.show_workout)
        nav.addWidget(self.workout_nav)
        self.pet_nav = QPushButton("◉   Pet Care")
        self.pet_nav.setObjectName("nav")
        self.pet_nav.setAccessibleName("Pet Care")
        self.pet_nav.setCheckable(True)
        self.pet_nav.clicked.connect(self.show_pets)
        nav.addWidget(self.pet_nav)
        self.meal_nav = QPushButton("◉   Meal Planner")
        self.meal_nav.setObjectName("nav")
        self.meal_nav.setAccessibleName("Meal Planner")
        self.meal_nav.setCheckable(True)
        self.meal_nav.clicked.connect(self.show_meals)
        nav.addWidget(self.meal_nav)
        self.maintenance_nav = QPushButton("◉   Home Maintenance")
        self.maintenance_nav.setObjectName("nav")
        self.maintenance_nav.setAccessibleName("Home Maintenance")
        self.maintenance_nav.setCheckable(True)
        self.maintenance_nav.clicked.connect(self.show_maintenance)
        nav.addWidget(self.maintenance_nav)
        self.calendar_nav = QPushButton("▦   Calendar")
        self.calendar_nav.setObjectName("nav")
        self.calendar_nav.setAccessibleName("Calendar")
        self.calendar_nav.setCheckable(True)
        self.calendar_nav.clicked.connect(self.show_calendar)
        nav.addWidget(self.calendar_nav)
        nav.addStretch()
        if self.settings_store is not None and self.data_directory is not None:
            settings = QPushButton("⚙   Settings")
            settings.setObjectName("nav")
            settings.setAccessibleName("Storage settings")
            settings.clicked.connect(self.show_storage_settings)
            nav.addWidget(settings)
        self.sidebar_profile = QLabel(f"◉   {self.profile_name}")
        self.sidebar_profile.setObjectName("muted")
        nav.addWidget(self.sidebar_profile)
        if self.on_sign_out is not None:
            sign_out = QPushButton("Sign out")
            sign_out.setObjectName("signOut")
            sign_out.clicked.connect(self.on_sign_out)
            nav.addWidget(sign_out)
        outer.addWidget(sidebar)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(88)
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(48, 0, 48, 0)
        topbar_layout.setSpacing(0)
        topbar_layout.addStretch(3)
        self.app_search = QLineEdit()
        self.app_search.setObjectName("appSearch")
        self.app_search.setAccessibleName("Search apps")
        self.app_search.setPlaceholderText("⌕  Search apps")
        self.app_search.setMinimumWidth(160)
        self.app_search.setMaximumWidth(440)
        self.app_search.setFixedHeight(48)
        self.app_search.returnPressed.connect(self._search_apps)
        topbar_layout.addWidget(self.app_search)
        topbar_layout.addStretch(1)
        self.theme_button = QPushButton("◉  Theme")
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setAccessibleName("Theme")
        self.theme_button.setStyleSheet(
            "background: #151027; border: 1px solid #292339; border-radius: 22px;"
            "padding: 10px 15px; font-weight: 700;"
        )
        theme_menu = QMenu(self.theme_button)
        theme_menu.setStyleSheet(
            "QMenu { background: #1a1533; color: #f3f4f6;"
            "border: 1px solid #302943; padding: 8px; }"
            "QMenu::item { padding: 8px 14px; }"
            "QMenu::item:selected { background: #302348; }"
        )
        for theme in THEMES:
            action = theme_menu.addAction(theme)
            action.triggered.connect(lambda _checked=False, name=theme: self._set_theme(name))
        self.theme_button.setMenu(theme_menu)
        topbar_layout.addWidget(self.theme_button)
        topbar_layout.addSpacing(14)
        self.profile_button = QPushButton("☾")
        self.profile_button.setObjectName("profileButton")
        self.profile_button.setAccessibleName("Profile")
        self.profile_button.setFixedSize(44, 44)
        self.profile_button.clicked.connect(self.show_profile)
        topbar_layout.addWidget(self.profile_button)
        content_layout.addWidget(topbar)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pages")
        self.pages.addWidget(self._build_dashboard())
        self.pages.addWidget(self._build_tasks())
        self.budget_page = BudgetPage(BudgetService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.budget_page)
        self.journal_page = JournalPage(JournalService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.journal_page)
        self.medicine_page = MedicinePage(MedicineService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.medicine_page)
        self.habit_page = HabitPage(HabitService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.habit_page)
        self.calorie_page = CaloriePage(CalorieService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.calorie_page)
        self.weight_page = WeightPage(WeightService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.weight_page)
        self.workout_page = WorkoutPage(WorkoutService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.workout_page)
        self.pet_page = PetPage(PetService(self.service.storage), self.profile_id,
                                self.show_medicine)
        self.pages.addWidget(self.pet_page)
        self.meal_page = MealPage(MealService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.meal_page)
        self.maintenance_page = MaintenancePage(
            MaintenanceService(self.service.storage), self.profile_id
        )
        self.pages.addWidget(self.maintenance_page)
        self.calendar_page = CalendarPage(CalendarService(self.service.storage), self.profile_id)
        self.pages.addWidget(self.calendar_page)
        self.profile_page = ProfilePage(ProfileService(self.service.storage),
                                        self.profile_id, self._profile_saved)
        self.pages.addWidget(self.profile_page)
        content_layout.addWidget(self.pages, 1)
        outer.addWidget(content, 1)
        self.topbar_layout = topbar_layout

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "topbar_layout"):
            margin = 24 if self.width() < 1050 else 48
            self.topbar_layout.setContentsMargins(margin, 0, margin, 0)
            self._layout_app_cards()

    def _search_apps(self) -> None:
        query = self.app_search.text().strip().casefold()
        if "budget" in query:
            self.show_budget()
        elif "task" in query:
            self.show_tasks()
        elif "journal" in query:
            self.show_journal()
        elif "medicine" in query or "dose" in query:
            self.show_medicine()
        elif "habit" in query:
            self.show_habits()
        elif "calorie" in query or "food" in query:
            self.show_calorie()
        elif "weight" in query or "weigh" in query:
            self.show_weight()
        elif "workout" in query or "exercise" in query:
            self.show_workout()
        elif "pet" in query or "animal" in query:
            self.show_pets()
        elif "meal" in query or "dinner" in query:
            self.show_meals()
        elif "maintenance" in query or "home care" in query:
            self.show_maintenance()
        elif "calendar" in query or "event" in query:
            self.show_calendar()
        elif "profile" in query or "account" in query:
            self.show_profile()
        elif "dashboard" in query or "home" in query:
            self.show_dashboard()

    def _profile_saved(self, view: ProfileView) -> None:
        self.profile_name = view.name
        self.sidebar_profile.setText(f"◉   {view.name}")
        self._set_profile_avatar(view)
        self.pages.widget(0).findChild(QLabel, "heading").setText(
            f"Welcome back, {view.name}"
        )

    def _set_profile_avatar(self, view: ProfileView) -> None:
        self.profile_button.setText(view.avatar_emoji)
        self.profile_button.setStyleSheet(
            f"background: {view.avatar_color}; color: #fff; border: 2px solid #a855f7;"
            "border-radius: 22px; padding: 0; font-size: 26px;"
        )

    def _set_theme(self, name: str) -> None:
        check_icon = (Path(__file__).parent / "assets" / "task-checked.svg").as_posix()
        self.setStyleSheet(_themed_style(STYLE.replace("__CHECK_ICON__", check_icon), name))
        page_styles = (
            (self.budget_page, BUDGET_STYLE),
            (self.journal_page, JOURNAL_STYLE),
            (self.medicine_page, MEDICINE_STYLE),
            (self.habit_page, HABIT_STYLE),
            (self.calorie_page, CALORIE_STYLE),
            (self.weight_page, WEIGHT_STYLE),
            (self.workout_page, WORKOUT_STYLE),
            (self.pet_page, PET_STYLE),
            (self.meal_page, MEAL_STYLE),
            (self.maintenance_page, MAINTENANCE_STYLE),
            (self.calendar_page, CALENDAR_STYLE),
            (self.profile_page, PROFILE_STYLE),
        )
        for page, style in page_styles:
            page.setStyleSheet(_themed_style(style, name))
        for calendar in self.findChildren(QCalendarWidget):
            style_calendar(calendar, THEMES[name])
        self.theme_button.setStyleSheet(_themed_style(
            "background: #151027; border: 1px solid #292339;"
            "border-radius: 22px; padding: 10px 15px; font-weight: 700;", name
        ))
        self.theme_button.menu().setStyleSheet(_themed_style(
            "QMenu { background: #1a1533; color: #f3f4f6;"
            "border: 1px solid #302943; padding: 8px; }"
            "QMenu::item { padding: 8px 14px; }"
            "QMenu::item:selected { background: #302348; }", name
        ))
        self.theme_button.setText("◉  Theme")

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        page.setObjectName("dashboardPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(48, 36, 48, 36)
        layout.setSpacing(0)

        eyebrow = QLabel("YOUR SPACE")
        eyebrow.setObjectName("eyebrow")
        layout.addWidget(eyebrow)
        layout.addSpacing(7)
        heading = QLabel(f"Welcome back, {self.profile_name}")
        heading.setTextFormat(Qt.TextFormat.PlainText)
        heading.setWordWrap(True)
        heading.setObjectName("heading")
        heading.setAccessibleName("Dashboard welcome")
        layout.addWidget(heading)
        subtitle = QLabel("A focused view of the things you chose for today.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("muted")
        layout.addWidget(subtitle)
        layout.addSpacing(42)

        section_row = QHBoxLayout()
        section = QLabel("Your apps")
        section.setObjectName("section")
        section_row.addWidget(section)
        section_row.addStretch()
        selected = QLabel("4 selected")
        selected.setObjectName("sectionMeta")
        section_row.addWidget(selected)
        layout.addLayout(section_row)
        layout.addSpacing(14)

        self.app_grid = QGridLayout()
        self.app_grid.setSpacing(16)
        self._app_columns = 0
        self.app_cards = (
            self._app_card("B", "Easy Budget", "Manage your money.", self.show_budget),
            self._app_card("T", "Task List", "Keep priorities clear.", self.show_tasks),
            self._app_card("J", "Easy Journal", "Capture your thoughts.", self.show_journal),
            self._app_card("M", "Medicine Tracker", "Keep doses on schedule.", self.show_medicine),
            self._app_card("H", "Habit Tracker", "Build small daily routines.", self.show_habits),
            self._app_card("C", "Calorie Tracker", "Track daily food intake.", self.show_calorie),
            self._app_card("W", "Weight Tracker", "Follow weight milestones.", self.show_weight),
            self._app_card("W", "Workout Tracker", "Log daily exercise.", self.show_workout),
            self._app_card("P", "Pet Care", "Keep care records for each pet.", self.show_pets),
            self._app_card("M", "Meal Planner", "Plan dinners for the week.", self.show_meals),
            self._app_card("H", "Home Maintenance", "Keep recurring care on schedule.",
                           self.show_maintenance),
            self._app_card("C", "Calendar", "Plan events in month or week view.",
                           self.show_calendar),
        )
        selected.setText(f"{len(self.app_cards)} selected")
        layout.addLayout(self.app_grid)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("dashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        self.dashboard_scroll = scroll
        scroll.viewport().installEventFilter(self)
        self._layout_app_cards()
        return scroll

    def eventFilter(self, watched, event) -> bool:
        if (hasattr(self, "dashboard_scroll")
                and watched is self.dashboard_scroll.viewport()
                and event.type() == QEvent.Type.Resize):
            self._layout_app_cards()
        return super().eventFilter(watched, event)

    def _layout_app_cards(self) -> None:
        margins = self.dashboard_scroll.widget().layout().contentsMargins()
        available = (self.dashboard_scroll.viewport().width()
                     - margins.left() - margins.right())
        columns = max(1, min(6, (available + 16) // (198 + 16)))
        if columns == self._app_columns:
            return
        self._app_columns = columns
        for card in self.app_cards:
            self.app_grid.removeWidget(card)
        for column in range(6):
            self.app_grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, card in enumerate(self.app_cards):
            self.app_grid.addWidget(card, index // columns, index % columns)

    def _app_card(
        self, icon_text: str, title_text: str, description_text: str,
        action: Callable[[], None],
    ) -> QPushButton:
        card = QPushButton()
        card.setObjectName("appCard")
        card.setAccessibleName(f"Open {title_text}")
        card.setMinimumWidth(198)
        card.setFixedHeight(136)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.clicked.connect(action)
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 16, 12, 16)
        card_layout.setSpacing(8)
        icon = QLabel(icon_text)
        icon.setObjectName("appIcon")
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon)
        app_text = QVBoxLayout()
        app_text.setSpacing(5)
        title = QLabel(title_text)
        title.setObjectName("appTitle")
        title.setWordWrap(True)
        title.setMinimumWidth(0)
        app_text.addWidget(title)
        description = QLabel(description_text)
        description.setObjectName("appDescription")
        description.setWordWrap(True)
        description.setMinimumWidth(0)
        app_text.addWidget(description)
        card_layout.addLayout(app_text, 1)
        arrow = QLabel("→")
        arrow.setObjectName("appArrow")
        card_layout.addWidget(arrow)
        return card

    def _show_page(self, index: int, title: str) -> None:
        self.pages.setCurrentIndex(index)
        for position, button in enumerate((
            self.dashboard_nav, self.tasks_nav, self.budget_nav,
            self.journal_nav, self.medicine_nav, self.habit_nav, self.calorie_nav,
            self.weight_nav, self.workout_nav, self.pet_nav, self.meal_nav,
            self.maintenance_nav, self.calendar_nav,
        )):
            button.setChecked(position == index)
        self.setWindowTitle(f"Solar Forge Life Helper — {title}")

    def show_dashboard(self) -> None:
        self._show_page(0, "Dashboard")

    def show_tasks(self) -> None:
        self._show_page(1, "Task List")
        self.refresh()

    def show_budget(self) -> None:
        self._show_page(2, "Easy Budget")
        self.budget_page.activate()

    def show_journal(self) -> None:
        self._show_page(3, "Easy Journal")
        self.journal_page.activate()

    def show_medicine(self) -> None:
        self._show_page(4, "Medicine Tracker")
        self.medicine_page.activate()

    def show_habits(self) -> None:
        self._show_page(5, "Habit Tracker")
        self.habit_page.activate()

    def show_calorie(self) -> None:
        self._show_page(6, "Calorie Tracker")
        self.calorie_page.activate()

    def show_weight(self) -> None:
        self._show_page(7, "Weight Tracker")
        self.weight_page.activate()

    def show_workout(self) -> None:
        self._show_page(8, "Workout Tracker")
        self.workout_page.activate()

    def show_pets(self) -> None:
        self._show_page(9, "Pet Care")
        self.pet_page.activate()

    def show_meals(self) -> None:
        self._show_page(10, "Meal Planner")
        self.meal_page.activate()

    def show_maintenance(self) -> None:
        self._show_page(11, "Home Maintenance")
        self.maintenance_page.activate()

    def show_calendar(self) -> None:
        self._show_page(12, "Calendar")
        self.calendar_page.activate()

    def show_profile(self) -> None:
        self._show_page(13, "Solar Forge Profile")
        self.profile_page.activate()

    def show_storage_settings(self) -> None:
        if self.settings_store is not None and self.data_directory is not None:
            StorageSettingsDialog(
                self.settings_store, self.data_directory, self,
                scheduler=self.backup_scheduler,
            ).exec()

    def _build_tasks(self) -> QWidget:

        content = QWidget()
        body = QVBoxLayout(content)
        body.setContentsMargins(48, 36, 48, 36)
        body.setSpacing(10)
        title = QLabel("Easy Task List")
        title.setObjectName("heading")
        body.addWidget(title)
        subtitle = QLabel(
            "Manage your daily tasks, track your accomplishments, and organize your day."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        body.addWidget(subtitle)
        self.status = QLabel("")
        self.status.setObjectName("error")
        self.status.setAccessibleName("Task status")
        body.addWidget(self.status)

        columns = QHBoxLayout()
        columns.setSpacing(32)
        left = QVBoxLayout()
        left.setSpacing(24)
        entry_card = QFrame()
        entry_card.setObjectName("card")
        entry_layout = QVBoxLayout(entry_card)
        entry_layout.setContentsMargins(24, 24, 24, 24)
        section = QLabel("Add New Task")
        section.setObjectName("section")
        entry_layout.addWidget(section)
        entry_row = QHBoxLayout()
        self.title_input = QLineEdit()
        self.title_input.setObjectName("taskTitle")
        self.title_input.setAccessibleName("Task title")
        self.title_input.setPlaceholderText("What needs to be done?")
        self.title_input.setMaxLength(200)
        self.title_input.returnPressed.connect(self.add_task)
        entry_row.addWidget(self.title_input, 1)
        self.add_button = QPushButton("Add Task")
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add_task)
        entry_row.addWidget(self.add_button)
        entry_layout.addLayout(entry_row)
        visibility_row = QHBoxLayout()
        visibility_label = QLabel("Visible to")
        visibility_label.setObjectName("muted")
        visibility_row.addWidget(visibility_label)
        self.task_visibility = QComboBox()
        self.task_visibility.setObjectName("taskVisibility")
        self.task_visibility.setAccessibleName("Task visibility")
        self.task_visibility.addItem("Only me", "private")
        self.task_visibility.addItem("Household", "household")
        visibility_row.addWidget(self.task_visibility)
        visibility_row.addStretch()
        entry_layout.addLayout(visibility_row)
        left.addWidget(entry_card)

        self.active_card, self.active_heading, self.active_layout = self._make_list("Active Tasks")
        self.completed_card, self.completed_heading, self.completed_layout = self._make_list(
            "Completed Tasks"
        )
        left.addWidget(self.active_card)
        left.addStretch()
        columns.addLayout(left, 1)
        columns.addWidget(self.completed_card, 1, Qt.AlignmentFlag.AlignTop)
        body.addLayout(columns)
        body.addStretch()
        return content

    def _make_list(self, title: str) -> tuple[QFrame, QLabel, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 24, 24, 24)
        heading = QLabel(title)
        heading.setObjectName("section")
        layout.addWidget(heading)
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #302943;")
        layout.addWidget(divider)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container.setObjectName("taskListContainer")
        rows = QVBoxLayout(container)
        rows.setAlignment(Qt.AlignmentFlag.AlignTop)
        rows.setSpacing(12)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)
        return card, heading, rows

    def _submit(self, action: Callable[[], object], done: Callable[[object], None]) -> None:
        self.status.clear()
        self._worker.submit(action, done)

    def _set_busy(self, busy: bool) -> None:
        self.add_button.setEnabled(not busy)
        self.title_input.setEnabled(not busy)
        self.task_visibility.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, (ValueError, RuntimeError)) else
            "The task could not be saved. Check the data location and try again."
        )

    def refresh(self) -> None:
        self._submit(lambda: self.service.list_tasks(self.profile_id), self._render_tasks)

    def add_task(self) -> None:
        title = self.title_input.text()
        if not title.strip():
            self.status.setText("Task title is required.")
            self.title_input.setFocus()
            return
        visibility = self.task_visibility.currentData()
        self._submit(
            lambda: self.service.add_task(self.profile_id, title, visibility), self._after_add
        )

    def _after_add(self, _result: object) -> None:
        self.title_input.clear()
        self.task_visibility.setCurrentIndex(0)
        self.title_input.setFocus()
        self.refresh()

    def toggle_task(self, task_id: int) -> None:
        self._submit(
            lambda: self.service.toggle_task(self.profile_id, task_id), lambda _: self.refresh()
        )

    def change_task_visibility(self, task_id: int, visibility: str) -> None:
        self._submit(
            lambda: self.service.set_visibility(self.profile_id, task_id, visibility),
            lambda _: self.refresh(),
        )

    def delete_task(self, task_id: int, title: str) -> None:
        if DeleteTaskDialog(title, self).exec() != QDialog.DialogCode.Accepted:
            return
        self._submit(
            lambda: self.service.delete_task(self.profile_id, task_id), lambda _: self.refresh()
        )

    def _render_tasks(self, result: object) -> None:
        active, completed = result
        self._render_list(self.active_layout, self.active_heading, "Active Tasks", active)
        self._render_list(
            self.completed_layout, self.completed_heading, "Completed Tasks", completed
        )
        self.active_card.findChild(QScrollArea).setFixedHeight(
            min(430, max(150, len(active) * 66))
        )
        self.completed_card.findChild(QScrollArea).setFixedHeight(
            min(430, max(150, len(completed) * 66))
        )

    def _render_list(
        self, layout: QVBoxLayout, heading: QLabel, title: str, tasks: list[TaskItem]
    ) -> None:
        heading.setText(f"{title} ({len(tasks)})")
        while layout.count():
            item = layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        if not tasks:
            empty = QLabel(
                "All caught up!\nNo active tasks. Create one above to get started."
                if title == "Active Tasks"
                else "No completed tasks yet.\nTick off tasks on the left as you finish them."
            )
            empty.setObjectName("muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setMinimumHeight(130)
            layout.addWidget(empty)
            return
        for task in tasks:
            row = QFrame()
            row.setObjectName("taskRow")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(14, 12, 14, 12)
            check = QCheckBox()
            check.setObjectName(f"taskCheck_{task.id}")
            check.setAccessibleName(f"Toggle {task.title}")
            check.setChecked(task.completed)
            check.toggled.connect(lambda _checked, task_id=task.id: self.toggle_task(task_id))
            row_layout.addWidget(check)
            text_column = QVBoxLayout()
            text_column.setSpacing(2)
            task_title = QLabel(task.title)
            task_title.setTextFormat(Qt.TextFormat.PlainText)
            task_title.setObjectName("completedTitle" if task.completed else "taskTitleText")
            task_title.setWordWrap(True)
            text_column.addWidget(task_title)
            if task.completed_at:
                completed_at = datetime.fromisoformat(task.completed_at).astimezone()
                completed_time = QLabel(f"Completed at {completed_at:%I:%M %p}")
                completed_time.setObjectName("completionTime")
                text_column.addWidget(completed_time)
            row_layout.addLayout(text_column, 1)
            if task.profile_id == self.profile_id:
                sharing = QPushButton(
                    "Household" if task.visibility == "household" else "Only me"
                )
                sharing.setObjectName(f"taskVisibility_{task.id}")
                sharing.setAccessibleName(f"Change visibility for {task.title}")
                next_visibility = (
                    "private" if task.visibility == "household" else "household"
                )
                sharing.clicked.connect(
                    lambda _checked=False, task_id=task.id, value=next_visibility:
                    self.change_task_visibility(task_id, value)
                )
                row_layout.addWidget(sharing)
                delete = QPushButton("✕")
                delete.setProperty("role", "delete")
                delete.setObjectName(f"taskDelete_{task.id}")
                delete.setAccessibleName(f"Delete {task.title}")
                delete.clicked.connect(
                    lambda _checked=False, task_id=task.id, name=task.title: self.delete_task(
                        task_id, name
                    )
                )
                row_layout.addWidget(delete)
            else:
                shared_label = QLabel("Household")
                shared_label.setObjectName("muted")
                row_layout.addWidget(shared_label)
            layout.addWidget(row)

    def closeEvent(self, event) -> None:
        self._worker.shutdown()
        self.budget_page.shutdown()
        self.journal_page.shutdown()
        self.medicine_page.shutdown()
        self.habit_page.shutdown()
        self.calorie_page.shutdown()
        self.weight_page.shutdown()
        self.workout_page.shutdown()
        self.pet_page.shutdown()
        self.meal_page.shutdown()
        self.maintenance_page.shutdown()
        self.calendar_page.shutdown()
        self.profile_page.shutdown()
        self.on_close()
        super().closeEvent(event)
