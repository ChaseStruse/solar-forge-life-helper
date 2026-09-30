"""Native weekly meal planner with favorite reuse and grocery list."""

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.meals import FavoriteItem, MealService, MealWeek, PlannedMeal
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#mealPage, QWidget#mealBody { background: #0a0712; }
QScrollArea#mealScroll { background: #0a0712; border: none; }
QFrame#mealCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QLabel#mealEyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#mealTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#mealHeading { color: #f3f4f6; font-size: 19px; font-weight: 700; }
QLabel#mealText { color: #f3f4f6; font-size: 14px; }
QLabel#mealMuted { color: #a1a1aa; }
QLabel#mealStatus { color: #fb7185; }
QLineEdit#mealInput, QTextEdit#mealIngredients, QComboBox#mealDay {
    background: #211b30; color: #f3f4f6; border: 1px solid #302943;
    border-radius: 9px; padding: 9px 11px; }
QComboBox#mealDay QAbstractItemView { background: #211b30; color: #f3f4f6; }
QPushButton#mealPrimary { background: #8b5cf6; color: white; border: none;
    border-radius: 9px; padding: 9px 14px; font-weight: 700; }
QPushButton#mealSecondary { background: #292143; color: #f3f4f6;
    border: 1px solid #483a64; border-radius: 9px; padding: 8px 12px; }
QPushButton#mealLink { background: transparent; color: #a78bfa;
    border: none; padding: 6px; font-weight: 700; }
QPushButton#mealClear { background: transparent; color: #a1a1aa;
    border: none; padding: 6px; }
QCheckBox#mealCheck { color: #a1a1aa; spacing: 7px; }
QCheckBox#mealCheck::indicator { width: 17px; height: 17px;
    border: 1px solid #6f588e; border-radius: 4px; background: #211b30; }
QCheckBox#mealCheck::indicator:checked { background: #8b5cf6;
    border-color: #8b5cf6; }
QScrollBar:vertical { background: #151027; width: 10px; }
QScrollBar::handle:vertical { background: #483a64; border-radius: 5px; min-height: 28px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def _label(text: str, name: str) -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(True)
    return item


def _card() -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("mealCard")
    box = QVBoxLayout(card)
    box.setContentsMargins(20, 18, 20, 18)
    box.setSpacing(10)
    return card, box


def _clear(layout: QVBoxLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if widget := item.widget():
            widget.deleteLater()
        elif nested := item.layout():
            _clear(nested)


class MealPage(QWidget):
    def __init__(self, service: MealService, profile_id: int):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.week_start = date.today() - timedelta(days=date.today().weekday())
        self._serial = 0
        self.setObjectName("mealPage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-meals")
        self._worker.busy_changed.connect(self._set_busy)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("mealScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("mealBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(18)
        self.header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        intro = QVBoxLayout()
        intro.addWidget(_label("PLAN ONCE, SHOP ONCE", "mealEyebrow"))
        intro.addWidget(_label("Meal Planner", "mealTitle"))
        intro.addWidget(_label(
            "A simple dinner plan with favorites you can reuse anytime.", "mealMuted"
        ))
        self.header.addLayout(intro, 1)
        nav = QHBoxLayout()
        self.previous_button = QPushButton("←")
        self.previous_button.setObjectName("mealSecondary")
        self.previous_button.setAccessibleName("Previous week")
        self.previous_button.clicked.connect(lambda: self._move_week(-7))
        nav.addWidget(self.previous_button)
        self.week_label = _label("", "mealText")
        self.week_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self.week_label)
        self.next_button = QPushButton("→")
        self.next_button.setObjectName("mealSecondary")
        self.next_button.setAccessibleName("Next week")
        self.next_button.clicked.connect(lambda: self._move_week(7))
        nav.addWidget(self.next_button)
        self.header.addLayout(nav)
        layout.addLayout(self.header)
        self.status = _label("", "mealStatus")
        self.status.setAccessibleName("Meal status")
        layout.addWidget(self.status)
        self.status.hide()
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.columns.setSpacing(24)
        self._build_week()
        self._build_side()
        layout.addLayout(self.columns)
        layout.addStretch()
        self._apply_responsive()

    def _build_week(self) -> None:
        left = QVBoxLayout()
        heading = QHBoxLayout()
        heading.addWidget(_label("This Week", "mealHeading"))
        heading.addStretch()
        heading.addWidget(_label("Dinners", "mealMuted"))
        left.addLayout(heading)
        self.days_layout = QVBoxLayout()
        self.days_layout.setSpacing(12)
        left.addLayout(self.days_layout)
        left.addStretch()
        self.columns.addLayout(left, 17)

    def _build_side(self) -> None:
        side = QVBoxLayout()
        side.setSpacing(16)
        self.favorites_card, favorites_box = _card()
        heading = QHBoxLayout()
        heading.addWidget(_label("Favorites", "mealHeading"))
        heading.addStretch()
        self.favorites_count = _label("0", "mealMuted")
        heading.addWidget(self.favorites_count)
        favorites_box.addLayout(heading)
        self.favorites_layout = QVBoxLayout()
        self.favorites_layout.setSpacing(8)
        favorites_box.addLayout(self.favorites_layout)
        self.new_favorite_button = QPushButton("+ New Favorite")
        self.new_favorite_button.setObjectName("mealLink")
        self.new_favorite_button.clicked.connect(
            lambda: self.favorite_form.setVisible(not self.favorite_form.isVisible())
        )
        favorites_box.addWidget(self.new_favorite_button)
        self.favorite_form = QWidget()
        form = QVBoxLayout(self.favorite_form)
        form.setContentsMargins(0, 0, 0, 0)
        form.addWidget(_label("MEAL NAME", "mealMuted"))
        self.favorite_name = QLineEdit()
        self.favorite_name.setObjectName("mealInput")
        self.favorite_name.setAccessibleName("Favorite meal name")
        self.favorite_name.setMaxLength(150)
        self.favorite_name.setPlaceholderText("Taco bowls")
        form.addWidget(self.favorite_name)
        form.addWidget(_label("GROCERY ITEMS — OPTIONAL, ONE PER LINE", "mealMuted"))
        self.favorite_ingredients = QTextEdit()
        self.favorite_ingredients.setObjectName("mealIngredients")
        self.favorite_ingredients.setAccessibleName("Favorite grocery items")
        self.favorite_ingredients.setPlaceholderText("Ground turkey\nTortillas\nSalsa")
        self.favorite_ingredients.setFixedHeight(104)
        form.addWidget(self.favorite_ingredients)
        self.save_favorite_button = QPushButton("Save Favorite")
        self.save_favorite_button.setObjectName("mealPrimary")
        self.save_favorite_button.clicked.connect(self.add_favorite)
        form.addWidget(self.save_favorite_button)
        favorites_box.addWidget(self.favorite_form)
        self.favorite_form.hide()
        side.addWidget(self.favorites_card)
        grocery_card, grocery_box = _card()
        grocery_heading = QHBoxLayout()
        grocery_heading.addWidget(_label("Grocery List", "mealHeading"))
        grocery_heading.addStretch()
        self.grocery_count = _label("0 items", "mealMuted")
        grocery_heading.addWidget(self.grocery_count)
        grocery_box.addLayout(grocery_heading)
        self.grocery_layout = QVBoxLayout()
        self.grocery_layout.setSpacing(8)
        grocery_box.addLayout(self.grocery_layout)
        side.addWidget(grocery_card)
        side.addStretch()
        self.columns.addLayout(side, 8)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_responsive()

    def _apply_responsive(self) -> None:
        self.header.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )
        self.columns.setDirection(
            QBoxLayout.Direction.TopToBottom if self.width() < 900
            else QBoxLayout.Direction.LeftToRight
        )

    def _move_week(self, days: int) -> None:
        self.week_start += timedelta(days=days)
        self.refresh()

    def activate(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self._serial += 1
        serial = self._serial
        selected = self.week_start
        self._worker.submit(
            lambda: self.service.view(self.profile_id, selected),
            lambda result: self._render(result) if serial == self._serial else None,
        )

    def _set_busy(self, busy: bool) -> None:
        self.previous_button.setEnabled(not busy)
        self.next_button.setEnabled(not busy)
        self.save_favorite_button.setEnabled(not busy)
        self.new_favorite_button.setEnabled(not busy)
        self.favorites_card.setEnabled(not busy)
        if hasattr(self, "days_widget"):
            self.days_widget.setEnabled(not busy)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(
            str(error) if isinstance(error, ValueError)
            else "The meal could not be saved. Please try again."
        )
        self.status.setStyleSheet("color: #fb7185;")
        self.status.show()

    def _show_success(self, message: str) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()
        self.refresh()

    def _render(self, result: MealWeek) -> None:
        self.week_start = result.start
        self.week_label.setText(
            f"{result.start:%b} {result.start.day} – {result.end:%b} {result.end.day}"
        )
        _clear(self.days_layout)
        self.days_widget = QWidget()
        days_box = QVBoxLayout(self.days_widget)
        days_box.setContentsMargins(0, 0, 0, 0)
        days_box.setSpacing(12)
        for day, plan in result.days:
            days_box.addWidget(self._day_card(day, plan))
        self.days_layout.addWidget(self.days_widget)
        self.favorites_count.setText(str(len(result.favorites)))
        _clear(self.favorites_layout)
        if not result.favorites:
            self.favorites_layout.addWidget(_label(
                "Save a meal as a favorite and it will be ready for any day.", "mealMuted"
            ))
        for favorite in result.favorites:
            self.favorites_layout.addWidget(self._favorite_row(favorite, result))
        self.grocery_count.setText(f"{len(result.groceries)} items")
        _clear(self.grocery_layout)
        if not result.groceries:
            self.grocery_layout.addWidget(_label(
                "Add favorites with grocery items to build this list automatically.",
                "mealMuted",
            ))
        for name, count in result.groceries:
            row = QHBoxLayout()
            check = QCheckBox(name)
            check.setObjectName("mealCheck")
            check.setAccessibleName(f"Grocery item {name}")
            row.addWidget(check, 1)
            if count > 1:
                row.addWidget(_label(f"× {count}", "mealMuted"))
            self.grocery_layout.addLayout(row)

    def _day_card(self, day: date, plan: PlannedMeal | None) -> QFrame:
        card, box = _card()
        box.setContentsMargins(18, 14, 18, 14)
        row = QHBoxLayout()
        day_box = QVBoxLayout()
        day_box.addWidget(_label(f"{day:%A}", "mealText"))
        day_box.addWidget(_label(f"{day:%b} {day.day}", "mealMuted"))
        row.addLayout(day_box, 0)
        row.addSpacing(16)
        if plan:
            detail = QVBoxLayout()
            detail.addWidget(_label(plan.name, "mealText"))
            if plan.ingredients:
                count = len(plan.ingredients.splitlines())
                detail.addWidget(_label(
                    f"{count} grocery {'item' if count == 1 else 'items'}", "mealMuted"
                ))
            row.addLayout(detail, 1)
            clear = QPushButton("Clear")
            clear.setObjectName("mealClear")
            clear.setAccessibleName(f"Clear {plan.name}")
            clear.clicked.connect(lambda: self._delete_plan(plan))
            row.addWidget(clear)
        else:
            form = QVBoxLayout()
            input_row = QHBoxLayout()
            name = QLineEdit()
            name.setObjectName("mealInput")
            name.setAccessibleName(f"Meal for {day:%A}")
            name.setPlaceholderText("What's for dinner?")
            name.setMaxLength(150)
            input_row.addWidget(name, 1)
            add = QPushButton("Add")
            add.setObjectName("mealPrimary")
            input_row.addWidget(add)
            form.addLayout(input_row)
            favorite = QCheckBox("Favorite")
            favorite.setObjectName("mealCheck")
            form.addWidget(favorite)
            add.clicked.connect(lambda: self._save_day(day, name.text(), favorite.isChecked()))
            row.addLayout(form, 1)
        box.addLayout(row)
        return card

    def _favorite_row(self, favorite: FavoriteItem, week: MealWeek) -> QWidget:
        widget = QWidget()
        box = QVBoxLayout(widget)
        box.setContentsMargins(0, 4, 0, 4)
        heading = QHBoxLayout()
        details = QVBoxLayout()
        details.addWidget(_label(favorite.name, "mealText"))
        if favorite.ingredients:
            details.addWidget(_label(
                f"{len(favorite.ingredients.splitlines())} items", "mealMuted"
            ))
        heading.addLayout(details, 1)
        use = QPushButton("Use")
        use.setObjectName("mealLink")
        heading.addWidget(use)
        remove = QPushButton("×")
        remove.setObjectName("mealClear")
        remove.setAccessibleName(f"Remove {favorite.name} favorite")
        remove.clicked.connect(lambda: self._delete_favorite(favorite))
        heading.addWidget(remove)
        box.addLayout(heading)
        use_form = QWidget()
        use_box = QHBoxLayout(use_form)
        use_box.setContentsMargins(0, 0, 0, 0)
        selected_day = QComboBox()
        selected_day.setObjectName("mealDay")
        selected_day.setAccessibleName(f"Choose day for {favorite.name}")
        for day, plan in week.days:
            suffix = f" · replace {plan.name}" if plan else ""
            selected_day.addItem(f"{day:%A}{suffix}", day)
        use_box.addWidget(selected_day, 1)
        add = QPushButton("Add")
        add.setObjectName("mealPrimary")
        add.clicked.connect(lambda: self._use_favorite(favorite, selected_day.currentData()))
        use_box.addWidget(add)
        box.addWidget(use_form)
        use_form.hide()
        use.clicked.connect(lambda: use_form.setVisible(not use_form.isVisible()))
        return widget

    def _save_day(self, day: date, name: str, favorite: bool) -> None:
        self._worker.submit(
            lambda: self.service.save_plan(self.profile_id, day, name,
                                           save_favorite=favorite),
            lambda _: self._show_success(f"{name.strip()} added to {day:%A}"),
        )

    def _use_favorite(self, favorite: FavoriteItem, day: date) -> None:
        self._worker.submit(
            lambda: self.service.save_plan(self.profile_id, day, favorite_id=favorite.id),
            lambda _: self._show_success(f"{favorite.name} added to {day:%A}"),
        )

    def _delete_plan(self, plan: PlannedMeal) -> None:
        self._worker.submit(
            lambda: self.service.delete_plan(self.profile_id, plan.id),
            lambda _: self._show_success("Meal cleared."),
        )

    def add_favorite(self) -> None:
        name = self.favorite_name.text()
        ingredients = self.favorite_ingredients.toPlainText()
        self._worker.submit(
            lambda: self.service.add_favorite(self.profile_id, name, ingredients),
            lambda _: self._after_favorite(name.strip()),
        )

    def _after_favorite(self, name: str) -> None:
        self.favorite_name.clear()
        self.favorite_ingredients.clear()
        self.favorite_form.hide()
        self._show_success(f"{name} saved as a favorite.")

    def _delete_favorite(self, favorite: FavoriteItem) -> None:
        self._worker.submit(
            lambda: self.service.delete_favorite(self.profile_id, favorite.id),
            lambda _: self._show_success(f"{favorite.name} removed from favorites."),
        )

    def shutdown(self) -> None:
        self._worker.shutdown()
