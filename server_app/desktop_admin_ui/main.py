from __future__ import annotations

import subprocess
import sys

import httpx
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from client_app.desktop_user_ui.process_control import pids_for_port, terminate_pids
from client_app.desktop_user_ui.ui_helpers import apply_app_theme, guarded, make_card, set_banner
from shared.config.settings import get_settings


class AdminWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.process: subprocess.Popen[str] | None = None
        self.setWindowTitle("Noctrix Launcher")
        self.resize(820, 600)
        self._build_ui()
        self.refresh_status()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(4000)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 16, 18, 18)
        title = QLabel("Noctrix Launcher")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.banner = QLabel("Runtime and first-run setup only. Use the client workbench for administration.")
        layout.addWidget(self.banner)

        runtime_card, runtime_layout = make_card("Runtime")
        runtime_form = QFormLayout()
        self.host_label = QLabel(self.settings.api_host)
        self.port_label = QLabel(str(self.settings.api_port))
        self.mode_label = QLabel(self.settings.environment)
        self.fingerprint_label = QLabel(self.settings.server_fingerprint)
        self.health_label = QLabel("unknown")
        self.setup_label = QLabel("unknown")
        self.pid_label = QLabel("none")
        for label, widget in [
            ("Bind", self.host_label),
            ("Port", self.port_label),
            ("Mode", self.mode_label),
            ("Fingerprint", self.fingerprint_label),
            ("Health", self.health_label),
            ("Setup", self.setup_label),
            ("Backend PIDs", self.pid_label),
        ]:
            runtime_form.addRow(label, widget)
        runtime_layout.addLayout(runtime_form)
        layout.addWidget(runtime_card)

        buttons = QHBoxLayout()
        for text, handler in [
            ("Start", self.start_service),
            ("Stop", self.stop_service),
            ("Kill", self.kill_service),
            ("Refresh", self.refresh_status),
            ("Open Client Workbench", self.open_client_workbench),
        ]:
            button = QPushButton(text)
            if text == "Open Client Workbench":
                button.setProperty("primary", True)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)

        setup_card, setup_layout = make_card("First-Run Setup")
        setup_form = QFormLayout()
        self.admin_username_input = QLineEdit("admin")
        self.admin_password_input = QLineEdit("admin12345")
        self.admin_password_input.setEchoMode(QLineEdit.Password)
        self.company_input = QLineEdit("Example Company")
        self.environment_box = QComboBox()
        self.environment_box.addItems(["demo", "production"])
        self.admin_name_input = QLineEdit("Noctrix Admin")
        self.admin_email_input = QLineEdit("admin@noctrix.local")
        for label, widget in [
            ("Company", self.company_input),
            ("Environment", self.environment_box),
            ("Admin Username", self.admin_username_input),
            ("Admin Password", self.admin_password_input),
            ("Admin Name", self.admin_name_input),
            ("Admin Email", self.admin_email_input),
        ]:
            setup_form.addRow(label, widget)
        setup_layout.addLayout(setup_form)

        apply_button = QPushButton("Apply Guided Setup")
        apply_button.clicked.connect(self.apply_setup)
        setup_layout.addWidget(apply_button)
        layout.addWidget(setup_card)
        layout.addStretch(1)
        self.setCentralWidget(root)
        set_banner(self.banner, "Start the backend here, then open the role-aware client workbench with this server preselected.")

    def start_service(self) -> None:
        existing = pids_for_port(self.settings.api_port)
        if existing:
            self.pid_label.setText(", ".join(str(pid) for pid in existing))
            set_banner(self.banner, f"Backend is already listening on port {self.settings.api_port}.", ok=False)
            return
        self.process = subprocess.Popen([sys.executable, "-m", "server_app.service.app"])
        set_banner(self.banner, "Managed backend service launched.")
        self.refresh_status()

    def stop_service(self) -> None:
        stopped = terminate_pids(self._known_pids(), force=False)
        set_banner(self.banner, f"Sent stop signal to: {', '.join(map(str, stopped)) or 'none'}.")
        self.refresh_status()

    def kill_service(self) -> None:
        stopped = terminate_pids(self._known_pids(), force=True)
        set_banner(self.banner, f"Sent kill signal to: {', '.join(map(str, stopped)) or 'none'}.", ok=not bool(stopped))
        self.refresh_status()

    def open_client_workbench(self) -> None:
        base_url = f"http://{self.settings.api_host}:{self.settings.api_port}/api/v1"
        fingerprint = self.fingerprint_label.text()
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "client_app.desktop_user_ui.main",
                "--base-url",
                base_url,
                "--fingerprint",
                fingerprint,
                "--profile-name",
                "Local Launcher Server",
            ]
        )
        set_banner(self.banner, "Opened client workbench with the local server profile.")

    def refresh_status(self) -> None:
        pids = self._known_pids()
        self.pid_label.setText(", ".join(str(pid) for pid in pids) if pids else "none")
        try:
            base_url = f"http://{self.settings.api_host}:{self.settings.api_port}"
            response = httpx.get(f"{base_url}/health", timeout=2)
            response.raise_for_status()
            self.health_label.setText(response.json()["status"])
            setup_response = httpx.get(f"{base_url}/api/v1/setup-wizard/status", timeout=2)
            setup_response.raise_for_status()
            setup = setup_response.json()
            self.setup_label.setText("configured" if setup["configured"] else "not configured")
            self.company_input.setText(setup["company_name"])
            self.environment_box.setCurrentText(setup["environment"])
            self.fingerprint_label.setText(setup.get("fingerprint") or "unknown")
        except Exception:
            self.health_label.setText("offline")
            self.setup_label.setText("unknown")

    def apply_setup(self) -> None:
        def action() -> None:
            response = httpx.post(
                f"http://{self.settings.api_host}:{self.settings.api_port}/api/v1/setup-wizard/bootstrap",
                json={
                    "company_name": self.company_input.text().strip(),
                    "environment": self.environment_box.currentText(),
                    "super_admin_username": self.admin_username_input.text().strip(),
                    "super_admin_full_name": self.admin_name_input.text().strip(),
                    "super_admin_email": self.admin_email_input.text().strip(),
                    "super_admin_password": self.admin_password_input.text(),
                    "import_sample_data": True,
                },
                timeout=5,
            )
            response.raise_for_status()
            self.refresh_status()
            QMessageBox.information(self, "Setup Applied", "Setup wizard configuration was saved.")

        guarded(self, "Setup Failed", action)

    def _known_pids(self) -> list[int]:
        pids = pids_for_port(self.settings.api_port)
        if self.process and self.process.poll() is None:
            pids.append(self.process.pid)
        return sorted(set(pids))


def main() -> None:
    app = QApplication(sys.argv)
    apply_app_theme(app)
    window = AdminWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
