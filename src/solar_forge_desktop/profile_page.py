"""Native Solar Forge Profile summary and personal-details form."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
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

from solar_forge_desktop.profile import AVATAR_COLORS, AVATAR_ICONS, ProfileService, ProfileView
from solar_forge_desktop.workers import BackgroundWorker

STYLE = """
QWidget#profilePage, QWidget#profileBody { background: #0a0712; }
QScrollArea#profileScroll { background: #0a0712; border: none; }
QFrame#profileCard { background: #1a1533; border: 1px solid #302943;
    border-radius: 16px; }
QLabel#profileEyebrow { color: #ec4899; font-size: 11px; font-weight: 700; }
QLabel#profileTitle { color: #f3f4f6; font-size: 32px; font-weight: 700; }
QLabel#profileHeading { color: #f3f4f6; font-size: 20px; font-weight: 700; }
QLabel#profileMuted { color: #a1a1aa; font-size: 13px; }
QLabel#profileBio { color: #f3f4f6; font-size: 14px; }
QLabel#profileStatus { color: #fb7185; font-size: 13px; }
QLineEdit#profileInput, QTextEdit#profileInput, QComboBox#profileInput {
    background: #211b30; color: #f3f4f6; border: 1px solid #39314e;
    border-radius: 9px; padding: 9px 11px; }
QComboBox#profileInput QAbstractItemView { background: #211b30; color: #f3f4f6; }
QPushButton#profilePrimary { background: #8b5cf6; color: white; border: 0;
    border-radius: 9px; padding: 10px 14px; font-weight: 700; }
QScrollBar:vertical { background: #151027; width: 10px; }
QScrollBar::handle:vertical { background: #483a64; border-radius: 5px; min-height: 28px; }
"""


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


class ProfilePage(QWidget):
    def __init__(self, service: ProfileService, profile_id: int,
                 on_saved: Callable[[ProfileView], None]):
        super().__init__()
        self.service = service
        self.profile_id = profile_id
        self.on_saved = on_saved
        self.setObjectName("profilePage")
        self.setStyleSheet(STYLE)
        self._build()
        self._worker = BackgroundWorker(self, "solar-forge-profile")
        self._worker.busy_changed.connect(self.save_button.setDisabled)
        self._worker.failed.connect(self._show_error)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("profileScroll")
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("profileBody")
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(48, 36, 48, 40)
        layout.setSpacing(16)
        layout.addWidget(_label("ACCOUNT", "profileEyebrow"))
        layout.addWidget(_label("Solar Forge Profile", "profileTitle"))
        layout.addWidget(_label("The personal details behind your Solar Forge Life space.",
                                "profileMuted"))
        self.status = _label("", "profileStatus")
        self.status.setAccessibleName("Profile status")
        self.status.hide()
        layout.addWidget(self.status)
        columns_container = QWidget()
        columns_container.setMaximumWidth(850)
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight, columns_container)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(24)
        self._build_summary()
        self._build_form()
        layout.addWidget(columns_container)
        layout.addStretch()
        self._apply_responsive()

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("profileCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 24, 24, 24)
        box.setSpacing(12)
        return card, box

    def _build_summary(self) -> None:
        self.summary_card, box = self._card()
        self.avatar = _label("🌙", "profileAvatar")
        self.avatar.setFixedSize(84, 84)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignHCenter)
        self.summary_name = _label("", "profileHeading")
        self.summary_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.summary_name)
        self.summary_username = _label("", "profileMuted")
        self.summary_username.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.summary_username)
        self.summary_bio = _label("", "profileBio")
        self.summary_bio.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.summary_bio)
        self.columns.addWidget(self.summary_card, 1, Qt.AlignmentFlag.AlignTop)

    def _field(self, box: QVBoxLayout, title: str, field: QWidget) -> None:
        box.addWidget(_label(title, "profileMuted"))
        box.addWidget(field)

    def _build_form(self) -> None:
        self.details_card, box = self._card()
        box.addWidget(_label("Personal Details", "profileHeading"))
        box.addWidget(_label(
            "Update how Solar Forge Life looks and feels for you. Dashboard apps and widgets "
            "are managed from the Dashboard.", "profileMuted"
        ))
        self.name_input = QLineEdit()
        self.name_input.setObjectName("profileInput")
        self.name_input.setAccessibleName("Display name")
        self.name_input.setMaxLength(100)
        self._field(box, "Display Name", self.name_input)
        self.bio_input = QTextEdit()
        self.bio_input.setObjectName("profileInput")
        self.bio_input.setAccessibleName("Bio or motto")
        self.bio_input.setFixedHeight(96)
        self._field(box, "Bio or Motto", self.bio_input)
        options = QHBoxLayout()
        colors = QVBoxLayout()
        self.color_input = QComboBox()
        self.color_input.setObjectName("profileInput")
        self.color_input.setAccessibleName("Avatar color")
        for color, label in AVATAR_COLORS:
            self.color_input.addItem(label, color)
        self._field(colors, "Avatar Color", self.color_input)
        options.addLayout(colors, 1)
        icons = QVBoxLayout()
        self.icon_input = QComboBox()
        self.icon_input.setObjectName("profileInput")
        self.icon_input.setAccessibleName("Avatar icon")
        for icon, label in AVATAR_ICONS:
            self.icon_input.addItem(f"{icon}  {label}", icon)
        self._field(icons, "Avatar Icon", self.icon_input)
        options.addLayout(icons, 1)
        box.addLayout(options)
        self.save_button = QPushButton("Save Profile")
        self.save_button.setObjectName("profilePrimary")
        self.save_button.clicked.connect(self.save)
        box.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.columns.addWidget(self.details_card, 2, Qt.AlignmentFlag.AlignTop)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "columns"):
            self._apply_responsive()

    def _apply_responsive(self) -> None:
        self.columns.setDirection(QBoxLayout.Direction.TopToBottom if self.width() < 900
                                  else QBoxLayout.Direction.LeftToRight)

    def activate(self) -> None:
        self._worker.submit(lambda: self.service.view(self.profile_id), self._render)

    def _render(self, view: ProfileView) -> None:
        self.summary_name.setText(view.name)
        self.summary_username.setText(f"@{view.username}" if view.username else "Local profile")
        self.summary_bio.setText(f"“{view.bio or 'Solar Forge Life Helper member'}”")
        self.avatar.setText(view.avatar_emoji)
        self.avatar.setStyleSheet(
            f"background: {view.avatar_color}; color: white; border-radius: 42px;"
            "font-size: 36px;"
        )
        self.name_input.setText(view.name)
        self.bio_input.setPlainText(view.bio)
        color_index = self.color_input.findData(view.avatar_color)
        self.color_input.setCurrentIndex(color_index if color_index >= 0 else 0)
        icon_index = self.icon_input.findData(view.avatar_emoji)
        self.icon_input.setCurrentIndex(icon_index if icon_index >= 0 else 0)

    def _show_error(self, error: Exception) -> None:
        self.status.setText(str(error) if isinstance(error, ValueError)
                            else "The profile could not be saved. Please try again.")
        self.status.setStyleSheet("color: #fb7185;")
        self.status.show()

    def save(self) -> None:
        name = self.name_input.text()
        bio = self.bio_input.toPlainText()
        color = self.color_input.currentData()
        icon = self.icon_input.currentData()
        self._worker.submit(
            lambda: self.service.update(self.profile_id, name, bio, color, icon),
            self._after_save,
        )

    def _after_save(self, view: ProfileView) -> None:
        self._render(view)
        self.on_saved(view)
        self.status.setText("Profile and preferences updated successfully!")
        self.status.setStyleSheet("color: #10b981;")
        self.status.show()

    def shutdown(self) -> None:
        self._worker.shutdown()
