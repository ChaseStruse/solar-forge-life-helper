"""Native login and sign-up views styled after the web account pages."""

from typing import Callable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from solar_forge_desktop.auth import AuthService

AUTH_STYLE = """
QWidget#authWindow { background: #0a0712; color: #f3f4f6; }
QFrame#authCard { background: #110d20; border: 1px solid #242035; border-radius: 18px; }
QLabel#authBrand { color: #8b5cf6; font-size: 23px; font-weight: 800; }
QLabel#authHeading { color: #f3f4f6; font-size: 30px; font-weight: 700; }
QLabel#authMuted, QLabel#authHint, QLabel#authSwitch { color: #71717a; }
QLabel#authLabel { color: #a1a1aa; font-size: 12px; font-weight: 600; }
QLabel#authError { color: #fb7185; }
QLineEdit { background: #1d192c; color: #f3f4f6; border: 1px solid #242035;
            border-radius: 10px; padding: 11px 15px; }
QLineEdit:focus { border-color: #8b5cf6; }
QPushButton#authSubmit { background: #8b5cf6; color: white; border: 1px solid #a56eff;
                         border-radius: 10px; padding: 11px; font-weight: 700; }
QPushButton#authSubmit:hover { background: #a06df9; }
QPushButton#authSwitchButton { background: transparent; color: #8b5cf6;
                               border: none; text-decoration: underline; }
"""


class AuthWindow(QWidget):
    def __init__(self, service: AuthService, on_authenticated: Callable[[int], None]):
        super().__init__()
        self.service = service
        self.on_authenticated = on_authenticated
        self._signup = False
        self.setObjectName("authWindow")
        self.setWindowTitle("Solar Forge Life Helper — Sign in")
        self.setMinimumSize(520, 570)
        self.resize(900, 700)
        self.setStyleSheet(AUTH_STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        outer.addStretch()
        row = QHBoxLayout()
        row.addStretch()
        card = QFrame()
        card.setObjectName("authCard")
        card.setFixedWidth(420)
        form = QVBoxLayout(card)
        form.setContentsMargins(32, 32, 32, 32)
        form.setSpacing(12)
        brand = QLabel("☀  Solar Forge Life")
        brand.setObjectName("authBrand")
        form.addWidget(brand)
        form.addSpacing(14)
        self.heading = QLabel()
        self.heading.setObjectName("authHeading")
        form.addWidget(self.heading)
        self.subtitle = QLabel()
        self.subtitle.setObjectName("authMuted")
        self.subtitle.setWordWrap(True)
        form.addWidget(self.subtitle)
        form.addSpacing(12)
        self.error = QLabel("")
        self.error.setObjectName("authError")
        self.error.setAccessibleName("Account error")
        self.error.setWordWrap(True)
        form.addWidget(self.error)
        for label_text in ("Username", "Password"):
            label = QLabel(label_text.upper())
            label.setObjectName("authLabel")
            form.addWidget(label)
            field = QLineEdit()
            field.setObjectName(label_text.lower())
            field.setAccessibleName(label_text)
            field.returnPressed.connect(self.submit)
            form.addWidget(field)
            if label_text == "Username":
                self.username = field
                field.setMaxLength(80)
            else:
                self.password = field
                field.setEchoMode(QLineEdit.EchoMode.Password)
        self.hint = QLabel(
            "Use at least 8 characters. Passwords are securely hashed and never stored "
            "as readable text."
        )
        self.hint.setObjectName("authHint")
        self.hint.setWordWrap(True)
        form.addWidget(self.hint)
        form.addSpacing(8)
        self.submit_button = QPushButton()
        self.submit_button.setObjectName("authSubmit")
        self.submit_button.clicked.connect(self.submit)
        form.addWidget(self.submit_button)
        switch_row = QHBoxLayout()
        switch_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.switch_label = QLabel()
        self.switch_label.setObjectName("authSwitch")
        switch_row.addWidget(self.switch_label)
        self.switch_button = QPushButton()
        self.switch_button.setObjectName("authSwitchButton")
        self.switch_button.clicked.connect(self.toggle_mode)
        switch_row.addWidget(self.switch_button)
        form.addLayout(switch_row)
        row.addWidget(card)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()
        self.set_signup(not service.has_accounts())

    def set_signup(self, signup: bool) -> None:
        self._signup = signup
        action = "Create account" if signup else "Sign in"
        self.setWindowTitle(f"Solar Forge Life Helper — {action}")
        self.heading.setText("Create your account" if signup else "Welcome back")
        self.subtitle.setText(
            "Your username and password stay on this device."
            if signup else "Sign in to your private local account."
        )
        self.hint.setVisible(signup)
        self.submit_button.setText("Create account" if signup else "Sign in")
        self.switch_label.setText("Already have an account?" if signup else "New here?")
        self.switch_button.setText("Sign in" if signup else "Create an account")
        self.password.clear()
        self.error.clear()
        self.username.setFocus()

    def toggle_mode(self) -> None:
        self.set_signup(not self._signup)

    def submit(self) -> None:
        self.error.clear()
        try:
            profile_id = (
                self.service.register(self.username.text(), self.password.text())
                if self._signup else self.service.login(self.username.text(), self.password.text())
            )
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        self.password.clear()
        self.setEnabled(False)
        # Let QLineEdit finish handling Return before its window can be destroyed.
        QTimer.singleShot(0, lambda: self.on_authenticated(profile_id))
