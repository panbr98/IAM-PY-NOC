from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
    QWidget,
)

from client_app.desktop_user_ui.api_client import (
    NoctrixApiClient,
    ServerProfileStore,
    build_discovery_candidates,
    discover_server_profiles,
    normalize_api_base_url,
)
from client_app.desktop_user_ui.ui_helpers import bind_combo, guarded, populate_table, selected_row_id, set_banner
from client_app.desktop_user_ui.process_control import pids_for_port, terminate_pids


DEFAULT_PROFILE = {
    "name": "Local Demo Server",
    "base_url": "http://127.0.0.1:8787/api/v1",
    "fingerprint": "DEMO-FINGERPRINT",
    "bootstrap_mode": "preset",
}

PORTAL_STEPS = [
    "Connection",
    "Home",
    "Request Access",
    "My Requests",
    "My Access",
    "My Approvals",
    "Delegations",
    "Admin Console",
]

ADMIN_ENDPOINTS = {
    "Dashboard Summary": ("GET", "/dashboard/summary", None),
    "Identities": ("GET", "/identities", {"username": "new.user", "full_name": "New User", "email": "new.user@example.local", "role": "employee", "manager_id": None}),
    "Systems": ("GET", "/systems", {"name": "New System", "description": "", "owner_identity_id": None}),
    "Resources": ("GET", "/resources", {"name": "New Resource", "system_id": 1, "requestable": True, "description": ""}),
    "Task Mappings": ("GET", "/task-mappings", {"system_id": 1, "resource_id": 1, "action": "grant", "task_type": "manual_provision", "default_owner_role": "operator", "sla_hours": 24}),
    "Requests": ("GET", "/access-requests", None),
    "Approvals": ("GET", "/approvals", None),
    "Assignments": ("GET", "/resource-assignments", None),
    "Provisioning Tasks": ("GET", "/provisioning/tasks", None),
    "Delegations": ("GET", "/delegations", {"delegator_identity_id": 1, "delegate_identity_id": 2, "scope": "approval", "starts_at": datetime.now().isoformat(), "ends_at": (datetime.now() + timedelta(days=7)).isoformat()}),
    "Audit": ("GET", "/audit", None),
    "Business Roles": ("GET", "/business-roles", {"name": "Business Role", "description": "", "requestable": True, "risk_level": "normal", "active": True, "technical_role_ids": [], "resource_ids": []}),
    "Technical Roles": ("GET", "/technical-roles", {"name": "Technical Role", "description": "", "requestable": True, "active": True, "resource_ids": []}),
    "Birthright Rules": ("GET", "/birthright-rules", {"name": "Birthright Rule", "attribute_name": "department", "operator": "equals", "expected_value": "Finance", "target_type": "resource", "target_id": 1, "active": True, "grant_basis": "birthright"}),
    "Attribute Rules": ("GET", "/attribute-access-rules", {"name": "Attribute Rule", "attribute_name": "department", "operator": "equals", "expected_value": "Finance", "target_type": "resource", "target_id": 1, "mode": "assign", "active": True}),
    "Access Policies": ("GET", "/access-policies", {"name": "Access Policy", "resource_id": None, "system_id": None, "business_role_id": None, "technical_role_id": None, "max_duration_days": 30, "privileged": False, "base_risk_score": 0, "require_justification": False, "active": True}),
    "SoD Policies": ("GET", "/sod-policies", {"name": "SoD Policy", "description": "", "mode": "warn", "severity": "high", "active": True, "resource_pairs": []}),
    "Risk Rules": ("GET", "/risk-rules", {"name": "Risk Rule", "condition_type": "urgency", "condition_value": "critical", "score": 25, "severity": "high", "active": True}),
    "Approval Policies": ("GET", "/approval-policies", {"name": "Approval Policy", "scope_type": "default", "scope_id": None, "min_risk_score": 0, "sequential": True, "active": True, "stages": [{"stage_order": 1, "mode": "all", "approver_type": "manager", "approver_value": "", "required_count": 1}]}),
    "Expiry Policies": ("GET", "/access-expiry-policies", {"name": "Expiry Policy", "resource_id": None, "business_role_id": None, "technical_role_id": None, "default_duration_days": 30, "active": True}),
    "Reconciliation Runs": ("GET", "/reconciliation/runs", {"name": "Client reconciliation", "system_id": None, "connector_id": None, "desired_access": [], "actual_access": []}),
    "Reconciliation Findings": ("GET", "/reconciliation/findings", None),
    "Certification Campaigns": ("GET", "/certifications/campaigns", {"name": "Client campaign", "scope": "all_assignments", "reviewer_identity_id": None}),
    "Certification Items": ("GET", "/certifications/items", None),
    "PAM Secrets": ("GET", "/pam/secrets", {"name": "Privileged Secret", "system_id": None, "resource_id": None, "account_username": "admin", "secret_value": "change-me", "rotation_interval_days": 30}),
    "PAM Checkouts": ("GET", "/pam/checkouts", None),
    "Connectors": ("GET", "/connectors", {"name": "CSV Dry Run", "connector_type": "csv", "system_id": None, "dry_run": True, "config": {}, "secret": ""}),
    "Connector Runs": ("GET", "/connector-runs", None),
    "Connector Queries": ("GET", "/connector-queries", {"name": "Group discovery", "system_id": 1, "connector_id": 1, "operation": "discover", "query": {}, "active": True}),
    "Jobs": ("GET", "/jobs", {"job_type": "reconciliation", "payload": {}, "run_after": None}),
    "SCIM Users": ("GET", "/scim/v2/Users", {"userName": "scim.user", "displayName": "SCIM User", "active": True, "emails": [{"value": "scim.user@example.local", "primary": True}]}),
    "SCIM Groups": ("GET", "/scim/v2/Groups", {"displayName": "SCIM Group", "members": []}),
}


class AdminWizard(QWizard):
    def __init__(self, title: str, pages: list[tuple[str, QWidget]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        for page_title, widget in pages:
            page = QWizardPage()
            page.setTitle(page_title)
            layout = QVBoxLayout(page)
            layout.addWidget(widget)
            self.addPage(page)


class ClientWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Noctrix Self-Service Portal")
        self.resize(1180, 760)
        self.profile_store = ServerProfileStore()
        self.profiles = self.profile_store.load() or [DEFAULT_PROFILE]
        self.profile_store.save(self.profiles)
        self.api_client: NoctrixApiClient | None = None
        self.current_identity: dict[str, Any] | None = None
        self.current_permissions: list[str] = []
        self.identities_by_id: dict[int, dict[str, Any]] = {}
        self.systems_by_id: dict[int, dict[str, Any]] = {}
        self.resources_by_id: dict[int, dict[str, Any]] = {}
        self.admin_system_rows_by_id: dict[int, dict[str, Any]] = {}
        self.admin_resource_rows_by_id: dict[int, dict[str, Any]] = {}
        self.admin_assignment_rows_by_id: dict[int, dict[str, Any]] = {}
        self.admin_scim_mapping_rows_by_id: dict[int, dict[str, Any]] = {}
        self.requests_by_id: dict[int, dict[str, Any]] = {}
        self.approvals_by_request_id: dict[int, dict[str, Any]] = {}
        self.admin_rows_by_id: dict[int, dict[str, Any]] = {}
        self._build_ui()
        self._load_profile_into_form(0)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)

        self.nav = QListWidget()
        self.nav.setFixedWidth(210)
        for step in PORTAL_STEPS:
            QListWidgetItem(step, self.nav)
        self.nav.currentRowChanged.connect(self._on_step_changed)
        layout.addWidget(self.nav)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        self.banner = QLabel("Choose a profile and sign in.")
        content_layout.addWidget(self.banner)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_connection_page())
        self.stack.addWidget(self._build_home_page())
        self.stack.addWidget(self._build_request_page())
        self.stack.addWidget(self._build_requests_page())
        self.stack.addWidget(self._build_access_page())
        self.stack.addWidget(self._build_approvals_page())
        self.stack.addWidget(self._build_delegations_page())
        self.stack.addWidget(self._build_admin_page())
        content_layout.addWidget(self.stack, 1)
        layout.addWidget(content, 1)
        self.setCentralWidget(root)
        self._refresh_profile_box()
        self.nav.setCurrentRow(0)
        set_banner(self.banner, "Bootstrap with a preset profile, LAN discovery, or a manually saved endpoint.")

    def _build_connection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.profile_box = QComboBox()
        self.profile_box.currentIndexChanged.connect(self.on_profile_changed)
        self.profile_name_input = QLineEdit()
        self.endpoint_input = QLineEdit()
        self.fingerprint_input = QLineEdit()
        self.username_input = QLineEdit("employee")
        self.password_input = QLineEdit("employee123")
        self.password_input.setEchoMode(QLineEdit.Password)
        for label, widget in [
            ("Saved Profile", self.profile_box),
            ("Profile Name", self.profile_name_input),
            ("Endpoint", self.endpoint_input),
            ("Fingerprint", self.fingerprint_input),
            ("Username", self.username_input),
            ("Password", self.password_input),
        ]:
            form.addRow(label, widget)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        for text, handler in [
            ("Save Profile", self.save_profile),
            ("Discover LAN Servers", self.discover_servers),
            ("Connect And Sign In", self.handle_connect),
            ("Refresh Workspace", self.refresh_workspace),
            ("Stop Local Backend", self.stop_local_backend),
            ("Kill Local Backend", self.kill_local_backend),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.discovery_results = QListWidget()
        self.discovery_results.itemDoubleClicked.connect(self.use_discovered_profile)
        layout.addWidget(self.discovery_results, 1)
        return page

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.home_summary = QLabel("Sign in to load your workspace.")
        self.home_summary.setWordWrap(True)
        layout.addWidget(self.home_summary)
        self.permission_table = QTableWidget()
        layout.addWidget(self.permission_table, 1)
        return page

    def _build_request_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.resource_box = QComboBox()
        self.request_urgency_box = QComboBox()
        self.request_urgency_box.addItems(["normal", "high", "critical"])
        self.reason_input = QLineEdit("Need this access for daily work")
        self.comments_input = QTextEdit()
        form.addRow("Resource", self.resource_box)
        form.addRow("Urgency", self.request_urgency_box)
        form.addRow("Reason", self.reason_input)
        form.addRow("Comments", self.comments_input)
        layout.addLayout(form)
        self.submit_request_button = QPushButton("Submit Access Request")
        self.submit_request_button.clicked.connect(self.submit_access_request)
        layout.addWidget(self.submit_request_button)
        self.request_status_label = QLabel("Sign in to load requestable resources.")
        layout.addWidget(self.request_status_label)
        layout.addStretch(1)
        return page

    def _build_requests_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.requests_table = QTableWidget()
        layout.addWidget(self.requests_table)
        return page

    def _build_access_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.assignments_table = QTableWidget()
        layout.addWidget(self.assignments_table)
        return page

    def _build_approvals_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.approvals_table = QTableWidget()
        self.approvals_table.itemSelectionChanged.connect(self._update_action_buttons)
        layout.addWidget(self.approvals_table)
        self.approval_comment_input = QLineEdit()
        self.approval_comment_input.setPlaceholderText("Approval comment")
        layout.addWidget(self.approval_comment_input)
        buttons = QHBoxLayout()
        self.approve_button = QPushButton("Approve Selected")
        self.approve_button.clicked.connect(lambda: self.decide_selected_approval("approve"))
        self.reject_button = QPushButton("Reject Selected")
        self.reject_button.clicked.connect(lambda: self.decide_selected_approval("reject"))
        buttons.addWidget(self.approve_button)
        buttons.addWidget(self.reject_button)
        layout.addLayout(buttons)
        self.approval_status_label = QLabel("Approvals load after sign-in.")
        layout.addWidget(self.approval_status_label)
        return page

    def _build_delegations_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.delegations_table = QTableWidget()
        layout.addWidget(self.delegations_table)
        form = QFormLayout()
        self.delegate_box = QComboBox()
        self.delegation_scope_box = QComboBox()
        self.delegation_scope_box.addItems(["access", "approval"])
        self.delegation_start_input = QDateTimeEdit(datetime.now())
        self.delegation_end_input = QDateTimeEdit(datetime.now() + timedelta(days=7))
        self.delegation_start_input.setCalendarPopup(True)
        self.delegation_end_input.setCalendarPopup(True)
        form.addRow("Delegate", self.delegate_box)
        form.addRow("Scope", self.delegation_scope_box)
        form.addRow("Starts", self.delegation_start_input)
        form.addRow("Ends", self.delegation_end_input)
        layout.addLayout(form)
        self.create_delegation_button = QPushButton("Create Delegation")
        self.create_delegation_button.clicked.connect(self.create_delegation)
        layout.addWidget(self.create_delegation_button)
        self.delegation_status_label = QLabel("Delegations load after sign-in.")
        layout.addWidget(self.delegation_status_label)
        return page

    def _build_admin_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.admin_status_label = QLabel("Sign in as an admin to manage server data from the client.")
        layout.addWidget(self.admin_status_label)

        self.admin_tabs = QTabWidget()
        self.admin_tabs.addTab(self._build_admin_catalog_tab(), "Systems & Resources")
        self.admin_tabs.addTab(self._build_admin_assignments_tab(), "Assignments")
        self.admin_tabs.addTab(self._build_admin_scim_tab(), "SCIM & Connectors")
        self.admin_tabs.addTab(self._build_admin_raw_tab(), "Raw API")
        layout.addWidget(self.admin_tabs, 1)
        self.load_admin_template()
        return page

    def _build_admin_catalog_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.admin_systems_table = QTableWidget()
        self.admin_systems_table.itemSelectionChanged.connect(self.on_admin_system_selected)
        layout.addWidget(self.admin_systems_table)

        system_form = QFormLayout()
        self.admin_system_name_input = QLineEdit()
        self.admin_system_description_input = QLineEdit()
        self.admin_system_owner_box = QComboBox()
        system_form.addRow("System Name", self.admin_system_name_input)
        system_form.addRow("Description", self.admin_system_description_input)
        system_form.addRow("Owner", self.admin_system_owner_box)
        layout.addLayout(system_form)

        system_buttons = QHBoxLayout()
        for text, handler in [
            ("New With Wizard", self.open_system_wizard),
            ("Edit With Wizard", self.open_system_wizard),
            ("Create System", self.create_admin_system),
            ("Update System", self.update_admin_system),
            ("Delete System", self.delete_admin_system),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            system_buttons.addWidget(button)
        layout.addLayout(system_buttons)

        self.admin_resources_table = QTableWidget()
        self.admin_resources_table.itemSelectionChanged.connect(self.on_admin_resource_selected)
        layout.addWidget(self.admin_resources_table)

        resource_form = QFormLayout()
        self.admin_resource_name_input = QLineEdit()
        self.admin_resource_system_box = QComboBox()
        self.admin_resource_requestable_input = QCheckBox()
        self.admin_resource_requestable_input.setChecked(True)
        self.admin_resource_description_input = QLineEdit()
        resource_form.addRow("Resource Name", self.admin_resource_name_input)
        resource_form.addRow("System", self.admin_resource_system_box)
        resource_form.addRow("Requestable", self.admin_resource_requestable_input)
        resource_form.addRow("Description", self.admin_resource_description_input)
        layout.addLayout(resource_form)

        resource_buttons = QHBoxLayout()
        for text, handler in [
            ("New Resource With Wizard", self.open_resource_wizard),
            ("Edit Resource With Wizard", self.open_resource_wizard),
            ("Create Resource", self.create_admin_resource),
            ("Update Resource", self.update_admin_resource),
            ("Delete Resource", self.delete_admin_resource),
            ("Refresh Catalog", self.refresh_admin_catalog),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            resource_buttons.addWidget(button)
        layout.addLayout(resource_buttons)
        return page

    def _build_admin_assignments_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.admin_assignments_table = QTableWidget()
        layout.addWidget(self.admin_assignments_table)

        controls = QHBoxLayout()
        self.expiring_days_input = QSpinBox()
        self.expiring_days_input.setRange(1, 365)
        self.expiring_days_input.setValue(30)
        self.revoke_assignment_notes_input = QLineEdit()
        self.revoke_assignment_notes_input.setPlaceholderText("Revocation notes")
        controls.addWidget(QLabel("Expiring Within Days"))
        controls.addWidget(self.expiring_days_input)
        controls.addWidget(self.revoke_assignment_notes_input)
        for text, handler in [
            ("Refresh Assignments", self.refresh_admin_assignments),
            ("Show Expiring Assignments", self.refresh_admin_expiring_assignments),
            ("Revoke Selected Assignment", self.revoke_selected_assignment),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            controls.addWidget(button)
        layout.addLayout(controls)
        return page

    def _build_admin_scim_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.admin_connectors_table = QTableWidget()
        layout.addWidget(self.admin_connectors_table)

        connector_form = QFormLayout()
        self.admin_connector_name_input = QLineEdit()
        self.admin_connector_type_box = QComboBox()
        self.admin_connector_type_box.addItems(["scim", "csv", "ldap", "ad", "google_workspace", "jira", "github", "rest"])
        self.admin_connector_system_box = QComboBox()
        self.admin_connector_dry_run_input = QCheckBox()
        self.admin_connector_dry_run_input.setChecked(True)
        connector_form.addRow("Connector Name", self.admin_connector_name_input)
        connector_form.addRow("Type", self.admin_connector_type_box)
        connector_form.addRow("System", self.admin_connector_system_box)
        connector_form.addRow("Dry Run", self.admin_connector_dry_run_input)
        layout.addLayout(connector_form)

        connector_buttons = QHBoxLayout()
        for text, handler in [
            ("New Connector Query With Wizard", self.open_connector_query_wizard),
            ("Edit Connector Query With Wizard", self.open_connector_query_wizard),
            ("Create Connector", self.create_admin_connector),
            ("Refresh Connectors", self.refresh_admin_scim),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            connector_buttons.addWidget(button)
        layout.addLayout(connector_buttons)

        self.admin_scim_users_table = QTableWidget()
        self.admin_scim_groups_table = QTableWidget()
        self.admin_scim_groups_table.itemSelectionChanged.connect(self.on_admin_scim_group_selected)
        self.admin_scim_mappings_table = QTableWidget()
        self.admin_scim_mappings_table.itemSelectionChanged.connect(self.on_admin_scim_mapping_selected)
        layout.addWidget(self.admin_scim_users_table)
        layout.addWidget(self.admin_scim_groups_table)
        layout.addWidget(self.admin_scim_mappings_table)

        mapping_form = QFormLayout()
        self.admin_scim_group_box = QComboBox()
        self.admin_scim_mapping_resource_box = QComboBox()
        self.admin_scim_mapping_active_input = QCheckBox()
        self.admin_scim_mapping_active_input.setChecked(True)
        mapping_form.addRow("SCIM Group", self.admin_scim_group_box)
        mapping_form.addRow("Resource", self.admin_scim_mapping_resource_box)
        mapping_form.addRow("Active", self.admin_scim_mapping_active_input)
        layout.addLayout(mapping_form)

        mapping_buttons = QHBoxLayout()
        for text, handler in [
            ("New SCIM Mapping With Wizard", self.open_scim_mapping_wizard),
            ("Edit SCIM Mapping With Wizard", self.open_scim_mapping_wizard),
            ("Create Group Mapping", self.create_admin_scim_mapping),
            ("Update Group Mapping", self.update_admin_scim_mapping),
            ("Delete Group Mapping", self.delete_admin_scim_mapping),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            mapping_buttons.addWidget(button)
        layout.addLayout(mapping_buttons)
        return page

    def open_connector_query_wizard(self) -> None:
        wizard = AdminWizard(
            "Connector Query Wizard",
            [
                ("Connector", QLabel("Choose system and connector")),
                ("Operation", QLabel("Discovery, import, reconciliation, or group sync")),
                ("Query JSON", QLabel("Configure query or preview payload JSON")),
                ("Review", QLabel("Review connector query before saving")),
            ],
            self,
        )
        wizard.exec()

    def open_scim_mapping_wizard(self) -> None:
        wizard = AdminWizard(
            "SCIM Mapping Wizard",
            [
                ("Connector And System", QLabel("Choose the SCIM connector context")),
                ("SCIM Group", QLabel("Choose source group")),
                ("Resource", QLabel("Choose target resource")),
                ("Active Flag", QLabel("Enable or disable mapping")),
                ("Review", QLabel("Review Groups:<id> to resources:<id> mapping")),
            ],
            self,
        )
        if wizard.exec():
            self.create_admin_scim_mapping()

    def _build_admin_raw_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()
        self.admin_endpoint_box = QComboBox()
        for label in ADMIN_ENDPOINTS:
            self.admin_endpoint_box.addItem(label)
        self.admin_endpoint_box.currentIndexChanged.connect(self.refresh_admin_endpoint)
        self.admin_path_input = QLineEdit()
        self.admin_id_input = QLineEdit()
        self.admin_id_input.setPlaceholderText("Selected row ID or explicit ID")
        form.addRow("Endpoint", self.admin_endpoint_box)
        form.addRow("Path", self.admin_path_input)
        form.addRow("ID", self.admin_id_input)
        layout.addLayout(form)
        self.admin_table = QTableWidget()
        self.admin_table.itemSelectionChanged.connect(self.on_admin_row_selected)
        layout.addWidget(self.admin_table, 1)
        self.admin_payload_input = QTextEdit()
        layout.addWidget(self.admin_payload_input, 1)
        buttons = QHBoxLayout()
        for text, handler in [
            ("Provisioning Mapping Wizard", self.open_provisioning_mapping_wizard),
            ("Refresh", self.refresh_admin_endpoint),
            ("Template", self.load_admin_template),
            ("Create", self.admin_create),
            ("Update", self.admin_update),
            ("Delete", self.admin_delete),
            ("POST Action", self.admin_post_action),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        layout.addLayout(buttons)
        return page

    def _on_step_changed(self, row: int) -> None:
        self.stack.setCurrentIndex(max(row, 0))
        self._update_action_buttons()

    def _refresh_profile_box(self) -> None:
        current_name = self.profile_name_input.text().strip()
        self.profile_box.blockSignals(True)
        self.profile_box.clear()
        self.profile_box.addItems([profile["name"] for profile in self.profiles])
        self.profile_box.blockSignals(False)
        if current_name:
            for index, profile in enumerate(self.profiles):
                if profile["name"] == current_name:
                    self.profile_box.setCurrentIndex(index)
                    break

    def _load_profile_into_form(self, index: int) -> None:
        if index < 0 or index >= len(self.profiles):
            return
        profile = self.profiles[index]
        self.profile_name_input.setText(profile["name"])
        self.endpoint_input.setText(profile["base_url"])
        self.fingerprint_input.setText(profile["fingerprint"])

    def on_profile_changed(self, index: int) -> None:
        self._load_profile_into_form(index)

    def save_profile(self) -> None:
        name = self.profile_name_input.text().strip() or "Manual Profile"
        base_url = normalize_api_base_url(self.endpoint_input.text())
        profile = {
            "name": name,
            "base_url": base_url,
            "fingerprint": self.fingerprint_input.text().strip(),
            "bootstrap_mode": "manual",
        }
        self.profiles = self.profile_store.upsert(profile)
        self._refresh_profile_box()
        set_banner(self.banner, f"Saved profile '{name}' for {base_url}.")

    def discover_servers(self) -> None:
        discovered = discover_server_profiles(build_discovery_candidates(self.profiles))
        self.discovery_results.clear()
        if not discovered:
            set_banner(self.banner, "No Noctrix servers responded to discovery.", ok=False)
            return
        for profile in discovered:
            item = QListWidgetItem(f"{profile['name']} | {profile['base_url']} | fp={profile['fingerprint']}")
            item.setData(Qt.UserRole, profile)
            self.discovery_results.addItem(item)
        set_banner(self.banner, f"Discovered {len(discovered)} reachable Noctrix server profile(s).")

    def use_discovered_profile(self, item: QListWidgetItem) -> None:
        profile = item.data(Qt.UserRole)
        if not isinstance(profile, dict):
            return
        self.profiles = self.profile_store.upsert(profile)
        self._refresh_profile_box()
        self.profile_name_input.setText(profile["name"])
        self.endpoint_input.setText(profile["base_url"])
        self.fingerprint_input.setText(profile["fingerprint"])
        set_banner(self.banner, f"Loaded discovered profile '{profile['name']}'.")

    def stop_local_backend(self) -> None:
        self._signal_local_backend(force=False)

    def kill_local_backend(self) -> None:
        self._signal_local_backend(force=True)

    def _signal_local_backend(self, *, force: bool) -> None:
        port = self._endpoint_port()
        if port is None:
            QMessageBox.warning(self, "No Port", "The endpoint does not include a usable port.")
            return
        stopped = terminate_pids(pids_for_port(port), force=force)
        verb = "kill" if force else "stop"
        set_banner(self.banner, f"Sent {verb} signal to local backend PIDs: {', '.join(map(str, stopped)) or 'none'}.")

    def _endpoint_port(self) -> int | None:
        parsed = urlparse(normalize_api_base_url(self.endpoint_input.text()))
        if parsed.port:
            return parsed.port
        if parsed.scheme == "https":
            return 443
        if parsed.scheme == "http":
            return 80
        return None

    def handle_connect(self) -> None:
        def action() -> None:
            self.api_client = NoctrixApiClient(self.endpoint_input.text().strip())
            info = self.api_client.get_server_info()
            if info["fingerprint"] != self.fingerprint_input.text().strip():
                raise ValueError("Server fingerprint does not match the selected trust value.")
            self.api_client.login(self.username_input.text().strip(), self.password_input.text())
            self.current_identity = self.api_client.get_me()
            self.current_permissions = self.api_client.get_permissions()
            set_banner(
                self.banner,
                f"Connected to {info['company_name']} as {self.current_identity['full_name']} ({self.current_identity['role']}).",
            )
            self.refresh_workspace()
            self.nav.setCurrentRow(1)

        guarded(self, "Connection Failed", action)

    def refresh_workspace(self) -> None:
        if not self.api_client or not self.current_identity:
            return

        def action() -> None:
            resources = self.api_client.get_resources()
            self.resources_by_id = {int(resource["id"]): resource for resource in resources}
            systems = self.api_client.get_systems() if "systems.read" in self.current_permissions else []
            self.systems_by_id = {int(system["id"]): system for system in systems}
            identities = self.api_client.get_identities() if "delegations.write" in self.current_permissions else []
            self.identities_by_id = {int(identity["id"]): identity for identity in identities}
            requests = self.api_client.get_access_requests()
            approvals_context = self.api_client.get_approval_instances()
            assignments = self.api_client.get_assignments()
            approvals = self.api_client.get_approvals() if "approvals.read" in self.current_permissions else []
            delegations = self.api_client.get_delegations() if "delegations.read" in self.current_permissions else []
            self._refresh_home(requests, assignments, approvals, delegations)
            self._refresh_request_page(resources)
            self._refresh_requests_page(requests, approvals_context)
            self._refresh_access_page(assignments)
            self._refresh_approvals_page(approvals)
            self._refresh_delegations_page(delegations, identities)
            if self._is_admin():
                self.refresh_admin_catalog()
                self.refresh_admin_assignments()
                self.refresh_admin_scim()
                self.refresh_admin_endpoint()
                self.admin_status_label.setText("Admin console enabled for this connection.")
            else:
                self.admin_status_label.setText("Admin console is locked for this role.")
            self._update_action_buttons()

        guarded(self, "Refresh Failed", action)

    def _refresh_home(
        self,
        requests: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        approvals: list[dict[str, Any]],
        delegations: list[dict[str, Any]],
    ) -> None:
        me = self.current_identity or {}
        self.home_summary.setText(
            f"{me.get('full_name', 'Signed in')} | requests={len(requests)} | access={len(assignments)} | "
            f"approvals={len(approvals)} | delegations={len(delegations)}"
        )
        populate_table(self.permission_table, [{"permission": item} for item in self.current_permissions], [("Permission", "permission")])

    def _refresh_request_page(self, resources: list[dict[str, Any]]) -> None:
        requestable = [resource for resource in resources if resource.get("requestable")]
        bind_combo(self.resource_box, requestable, self._resource_label)
        can_submit = "requests.write" in self.current_permissions and bool(requestable)
        self.submit_request_button.setEnabled(can_submit)
        self.request_status_label.setText(
            "Resources loaded. Submit a request for yourself."
            if can_submit
            else "No requestable resources are available for this role."
        )

    def _refresh_requests_page(self, requests: list[dict[str, Any]], approval_instances: list[dict[str, Any]]) -> None:
        stages_by_request: dict[int, int] = {}
        for stage in approval_instances:
            request_id = int(stage["access_request_id"])
            stages_by_request[request_id] = stages_by_request.get(request_id, 0) + 1
        rows = []
        self.requests_by_id = {}
        for item in requests:
            row = dict(item)
            row["resource"] = self._resource_name(int(item["resource_id"]))
            row["beneficiary"] = self._identity_name(int(item["beneficiary_identity_id"]))
            row["stages"] = stages_by_request.get(int(item["id"]), 0)
            rows.append(row)
            self.requests_by_id[int(item["id"])] = row
        populate_table(
            self.requests_table,
            rows,
            [("ID", "id"), ("Status", "status"), ("Resource", "resource"), ("Risk", "risk_level"), ("Score", "risk_score"), ("Stages", "stages"), ("Summary", "policy_evaluation_summary")],
        )

    def _refresh_access_page(self, assignments: list[dict[str, Any]]) -> None:
        rows = []
        for item in assignments:
            row = dict(item)
            row["resource"] = self._resource_name(int(item["resource_id"]))
            rows.append(row)
        populate_table(
            self.assignments_table,
            rows,
            [("ID", "id"), ("Resource", "resource"), ("Status", "status"), ("Source", "source_type"), ("Expires", "expires_at"), ("Risk", "risk_score")],
        )

    def _refresh_approvals_page(self, approvals: list[dict[str, Any]]) -> None:
        self.approvals_by_request_id = {int(item["access_request_id"]): item for item in approvals}
        populate_table(
            self.approvals_table,
            approvals,
            [("Request", "access_request_id"), ("Status", "status"), ("Decision", "decision"), ("Approver", "approver_identity_id")],
            id_key="access_request_id",
        )
        self.approval_status_label.setText(f"Loaded {len(approvals)} approvals.")

    def _refresh_delegations_page(self, delegations: list[dict[str, Any]], identities: list[dict[str, Any]]) -> None:
        rows = []
        for item in delegations:
            row = dict(item)
            row["delegator"] = self._identity_name(int(item["delegator_identity_id"]))
            row["delegate"] = self._identity_name(int(item["delegate_identity_id"]))
            rows.append(row)
        populate_table(self.delegations_table, rows, [("ID", "id"), ("Scope", "scope"), ("Status", "status"), ("Delegator", "delegator"), ("Delegate", "delegate")])
        current_id = int(self.current_identity["id"]) if self.current_identity else None
        bind_combo(self.delegate_box, [item for item in identities if item["id"] != current_id], lambda item: f"{item['full_name']} ({item['role']})")
        self.create_delegation_button.setEnabled("delegations.write" in self.current_permissions and self.delegate_box.count() > 0)
        self.delegation_status_label.setText(f"Loaded {len(delegations)} delegations.")

    def submit_access_request(self) -> None:
        if not self.api_client or not self.current_identity:
            QMessageBox.warning(self, "Not Connected", "Connect to a Noctrix server first.")
            return
        resource_id = self.resource_box.currentData()
        if resource_id is None:
            QMessageBox.warning(self, "No Resource", "No requestable resource is loaded.")
            return

        def action() -> None:
            result = self.api_client.create_access_request(
                beneficiary_identity_id=int(self.current_identity["id"]),
                resource_id=int(resource_id),
                reason=self.reason_input.text().strip(),
                urgency=self.request_urgency_box.currentText(),
                comments=self.comments_input.toPlainText().strip(),
            )
            self.request_status_label.setText(f"Submitted request #{result['id']} with status {result['status']}.")
            self.refresh_workspace()

        guarded(self, "Request Failed", action)

    def decide_selected_approval(self, decision: str) -> None:
        if not self.api_client:
            return
        request_id = selected_row_id(self.approvals_table)
        if request_id is None:
            QMessageBox.warning(self, "No Approval Selected", "Select an approval first.")
            return

        def action() -> None:
            result = self.api_client.decide_approval(request_id, decision, self.approval_comment_input.text().strip())
            self.approval_status_label.setText(f"Updated request #{result['access_request_id']} with decision {result['decision']}.")
            self.approval_comment_input.clear()
            self.refresh_workspace()

        guarded(self, "Approval Failed", action)

    def create_delegation(self) -> None:
        if not self.api_client or not self.current_identity:
            return
        delegate_id = self.delegate_box.currentData()
        if delegate_id is None:
            QMessageBox.warning(self, "No Delegate", "Select a delegate identity first.")
            return

        def action() -> None:
            result = self.api_client.create_delegation(
                delegator_identity_id=int(self.current_identity["id"]),
                delegate_identity_id=int(delegate_id),
                scope=self.delegation_scope_box.currentText(),
                starts_at=self.delegation_start_input.dateTime().toPython().isoformat(),
                ends_at=self.delegation_end_input.dateTime().toPython().isoformat(),
            )
            self.delegation_status_label.setText(f"Created delegation #{result['id']} with status {result['status']}.")
            self.refresh_workspace()

        guarded(self, "Delegation Failed", action)

    def refresh_admin_catalog(self) -> None:
        if not self.api_client or not self._is_admin():
            return

        def action() -> None:
            systems = self.api_client.get_systems()
            resources = self.api_client.get_resources()
            identities = self.api_client.get_identities()
            self.systems_by_id = {int(item["id"]): item for item in systems}
            self.resources_by_id = {int(item["id"]): item for item in resources}
            self.identities_by_id = {int(item["id"]): item for item in identities}
            self.admin_system_rows_by_id = {int(item["id"]): item for item in systems}
            bind_combo(self.admin_system_owner_box, identities, lambda item: f"{item['full_name']} ({item['role']})", include_none=True)
            bind_combo(self.admin_resource_system_box, systems, lambda item: item["name"])
            bind_combo(self.admin_connector_system_box, systems, lambda item: item["name"], include_none=True)
            bind_combo(self.admin_scim_mapping_resource_box, resources, self._resource_label_with_system)
            populate_table(
                self.admin_systems_table,
                [
                    {
                        **item,
                        "owner": self._identity_name(int(item["owner_identity_id"])) if item.get("owner_identity_id") else "",
                    }
                    for item in systems
                ],
                [("ID", "id"), ("System", "name"), ("Owner", "owner"), ("Description", "description")],
            )
            resource_rows = []
            self.admin_resource_rows_by_id = {}
            for item in resources:
                row = dict(item)
                row["system_name"] = self._system_name(int(item["system_id"]))
                resource_rows.append(row)
                self.admin_resource_rows_by_id[int(item["id"])] = row
            populate_table(
                self.admin_resources_table,
                resource_rows,
                [("ID", "id"), ("Resource", "name"), ("System", "system_name"), ("Requestable", "requestable"), ("Description", "description")],
            )

        guarded(self, "Catalog Refresh Failed", action)

    def open_system_wizard(self) -> None:
        wizard = AdminWizard(
            "System Wizard",
            [
                ("Basics", QLabel("System name and description")),
                ("Owner Selection", QLabel("Choose an owner identity")),
                ("Review", QLabel("Review system details before saving")),
            ],
            self,
        )
        if wizard.exec():
            self._mutate_admin_system(selected_row_id(self.admin_systems_table))

    def open_resource_wizard(self) -> None:
        wizard = AdminWizard(
            "Resource Wizard",
            [
                ("System Selection", QLabel("Every resource requires a system")),
                ("Resource Basics", QLabel("Name, description, and requestability")),
                ("Provisioning Mode", QLabel("Manual or automatic provisioning task mapping")),
                ("Optional SCIM Group Mapping", QLabel("Connect a SCIM group to this resource")),
                ("Review", QLabel("Review resource details before saving")),
            ],
            self,
        )
        if wizard.exec():
            self._mutate_admin_resource(selected_row_id(self.admin_resources_table))

    def open_provisioning_mapping_wizard(self) -> None:
        wizard = AdminWizard(
            "Provisioning Mapping Wizard",
            [
                ("Resource", QLabel("Choose system and resource")),
                ("Trigger", QLabel("Choose trigger_event and action")),
                ("Provisioning Mode", QLabel("Manual queue or automatic connector execution")),
                ("Connector Payload", QLabel("Optional connector query and payload template JSON")),
                ("Review", QLabel("Review task mapping before saving")),
            ],
            self,
        )
        wizard.exec()

    def create_admin_system(self) -> None:
        self._mutate_admin_system(None)

    def update_admin_system(self) -> None:
        system_id = selected_row_id(self.admin_systems_table)
        if system_id is None:
            QMessageBox.warning(self, "No System Selected", "Select a system first.")
            return
        self._mutate_admin_system(system_id)

    def delete_admin_system(self) -> None:
        if not self.api_client:
            return
        system_id = selected_row_id(self.admin_systems_table)
        if system_id is None:
            QMessageBox.warning(self, "No System Selected", "Select a system first.")
            return

        def action() -> None:
            self.api_client.delete_system(system_id)
            self.refresh_admin_catalog()

        guarded(self, "System Delete Failed", action)

    def _mutate_admin_system(self, system_id: int | None) -> None:
        if not self.api_client:
            return
        owner_id = self.admin_system_owner_box.currentData()

        def action() -> None:
            if system_id is None:
                self.api_client.create_system(
                    name=self.admin_system_name_input.text().strip(),
                    description=self.admin_system_description_input.text().strip(),
                    owner_identity_id=owner_id,
                )
            else:
                self.api_client.update_system(
                    system_id,
                    name=self.admin_system_name_input.text().strip(),
                    description=self.admin_system_description_input.text().strip(),
                    owner_identity_id=owner_id,
                )
            self.refresh_admin_catalog()

        guarded(self, "System Save Failed", action)

    def on_admin_system_selected(self) -> None:
        system_id = selected_row_id(self.admin_systems_table)
        if system_id is None:
            return
        row = self.admin_system_rows_by_id.get(system_id, {})
        self.admin_system_name_input.setText(str(row.get("name", "")))
        self.admin_system_description_input.setText(str(row.get("description", "")))
        bind_combo(
            self.admin_system_owner_box,
            self.identities_by_id.values(),
            lambda item: f"{item['full_name']} ({item['role']})",
            include_none=True,
            current=row.get("owner_identity_id"),
        )

    def create_admin_resource(self) -> None:
        self._mutate_admin_resource(None)

    def update_admin_resource(self) -> None:
        resource_id = selected_row_id(self.admin_resources_table)
        if resource_id is None:
            QMessageBox.warning(self, "No Resource Selected", "Select a resource first.")
            return
        self._mutate_admin_resource(resource_id)

    def delete_admin_resource(self) -> None:
        if not self.api_client:
            return
        resource_id = selected_row_id(self.admin_resources_table)
        if resource_id is None:
            QMessageBox.warning(self, "No Resource Selected", "Select a resource first.")
            return

        def action() -> None:
            self.api_client.delete_resource(resource_id)
            self.refresh_admin_catalog()

        guarded(self, "Resource Delete Failed", action)

    def _mutate_admin_resource(self, resource_id: int | None) -> None:
        if not self.api_client:
            return
        system_id = self.admin_resource_system_box.currentData()
        if system_id is None:
            QMessageBox.warning(self, "No System", "Select a system for the resource.")
            return

        def action() -> None:
            if resource_id is None:
                self.api_client.create_resource(
                    name=self.admin_resource_name_input.text().strip(),
                    system_id=int(system_id),
                    requestable=self.admin_resource_requestable_input.isChecked(),
                    description=self.admin_resource_description_input.text().strip(),
                )
            else:
                self.api_client.update_resource(
                    resource_id,
                    name=self.admin_resource_name_input.text().strip(),
                    system_id=int(system_id),
                    requestable=self.admin_resource_requestable_input.isChecked(),
                    description=self.admin_resource_description_input.text().strip(),
                )
            self.refresh_admin_catalog()

        guarded(self, "Resource Save Failed", action)

    def on_admin_resource_selected(self) -> None:
        resource_id = selected_row_id(self.admin_resources_table)
        if resource_id is None:
            return
        row = self.admin_resource_rows_by_id.get(resource_id, {})
        self.admin_resource_name_input.setText(str(row.get("name", "")))
        self.admin_resource_description_input.setText(str(row.get("description", "")))
        self.admin_resource_requestable_input.setChecked(bool(row.get("requestable", True)))
        bind_combo(self.admin_resource_system_box, self.systems_by_id.values(), lambda item: item["name"], current=row.get("system_id"))

    def refresh_admin_assignments(self) -> None:
        if not self.api_client or not self._is_admin():
            return

        def action() -> None:
            self._populate_admin_assignments(self.api_client.get_assignments(), "Loaded assignments.")

        guarded(self, "Assignment Refresh Failed", action)

    def refresh_admin_expiring_assignments(self) -> None:
        if not self.api_client or not self._is_admin():
            return

        def action() -> None:
            self._populate_admin_assignments(
                self.api_client.get_expiring_assignments(self.expiring_days_input.value()),
                "Loaded expiring assignments.",
            )

        guarded(self, "Expiring Assignment Refresh Failed", action)

    def revoke_selected_assignment(self) -> None:
        if not self.api_client:
            return
        assignment_id = selected_row_id(self.admin_assignments_table)
        if assignment_id is None:
            QMessageBox.warning(self, "No Assignment Selected", "Select an assignment first.")
            return

        def action() -> None:
            self.api_client.revoke_assignment(assignment_id, self.revoke_assignment_notes_input.text().strip())
            self.refresh_admin_assignments()

        guarded(self, "Assignment Revoke Failed", action)

    def _populate_admin_assignments(self, assignments: list[dict[str, Any]], message: str) -> None:
        rows = []
        self.admin_assignment_rows_by_id = {}
        for item in assignments:
            row = dict(item)
            resource_id = int(item["resource_id"])
            resource = self.resources_by_id.get(resource_id, {})
            row["identity"] = self._identity_name(int(item["identity_id"]))
            row["resource"] = self._resource_name(resource_id)
            row["system_name"] = self._system_name(int(resource["system_id"])) if resource.get("system_id") else ""
            rows.append(row)
            self.admin_assignment_rows_by_id[int(item["id"])] = row
        populate_table(
            self.admin_assignments_table,
            rows,
            [
                ("ID", "id"),
                ("Identity", "identity"),
                ("Resource", "resource"),
                ("System", "system_name"),
                ("Status", "status"),
                ("Source", "source_type"),
                ("Expires", "expires_at"),
                ("Risk", "risk_score"),
                ("Governance", "governance_state"),
            ],
        )
        self.admin_status_label.setText(f"{message} {len(rows)} row(s).")

    def refresh_admin_scim(self) -> None:
        if not self.api_client or not self._is_admin():
            return

        def action() -> None:
            connectors = self.api_client.get_connectors()
            users = self.api_client.list_scim_users()
            groups = self.api_client.list_scim_groups()
            mappings = self.api_client.list_scim_mappings()
            bind_combo(self.admin_scim_group_box, groups, lambda item: item["displayName"])
            populate_table(
                self.admin_connectors_table,
                [
                    {
                        **item,
                        "system_name": self._system_name(int(item["system_id"])) if item.get("system_id") else "",
                    }
                    for item in connectors
                ],
                [("ID", "id"), ("Name", "name"), ("Type", "connector_type"), ("System", "system_name"), ("Status", "status"), ("Dry Run", "dry_run")],
            )
            populate_table(self.admin_scim_users_table, users, [("SCIM ID", "id"), ("User", "userName"), ("Identity", "displayName"), ("Active", "active")])
            populate_table(self.admin_scim_groups_table, groups, [("SCIM ID", "id"), ("Group", "displayName"), ("Members", "members")])
            mapping_rows = []
            self.admin_scim_mapping_rows_by_id = {}
            for item in mappings:
                row = dict(item)
                if item.get("resource_id"):
                    row["resource"] = self._resource_name(int(item["resource_id"]))
                mapping_rows.append(row)
                self.admin_scim_mapping_rows_by_id[int(item["id"])] = row
            populate_table(
                self.admin_scim_mappings_table,
                mapping_rows,
                [("ID", "id"), ("SCIM Group", "scim_group_id"), ("Resource", "resource"), ("Source", "source_path"), ("Target", "target_path"), ("Active", "active")],
            )
            self.admin_status_label.setText("SCIM users map to identities; SCIM group mappings target resources.")

        guarded(self, "SCIM Refresh Failed", action)

    def create_admin_connector(self) -> None:
        if not self.api_client:
            return
        system_id = self.admin_connector_system_box.currentData()

        def action() -> None:
            self.api_client.create_connector(
                name=self.admin_connector_name_input.text().strip(),
                connector_type=self.admin_connector_type_box.currentText(),
                system_id=int(system_id) if system_id is not None else None,
                dry_run=self.admin_connector_dry_run_input.isChecked(),
                config={},
            )
            self.refresh_admin_scim()

        guarded(self, "Connector Create Failed", action)

    def create_admin_scim_mapping(self) -> None:
        self._mutate_admin_scim_mapping(None)

    def update_admin_scim_mapping(self) -> None:
        mapping_id = selected_row_id(self.admin_scim_mappings_table)
        if mapping_id is None:
            QMessageBox.warning(self, "No Mapping Selected", "Select a SCIM mapping first.")
            return
        self._mutate_admin_scim_mapping(mapping_id)

    def delete_admin_scim_mapping(self) -> None:
        if not self.api_client:
            return
        mapping_id = selected_row_id(self.admin_scim_mappings_table)
        if mapping_id is None:
            QMessageBox.warning(self, "No Mapping Selected", "Select a SCIM mapping first.")
            return

        def action() -> None:
            self.api_client.delete_scim_mapping(mapping_id)
            self.refresh_admin_scim()

        guarded(self, "SCIM Mapping Delete Failed", action)

    def _mutate_admin_scim_mapping(self, mapping_id: int | None) -> None:
        if not self.api_client:
            return
        scim_group_id = self.admin_scim_group_box.currentData()
        resource_id = self.admin_scim_mapping_resource_box.currentData()
        if scim_group_id is None or resource_id is None:
            QMessageBox.warning(self, "Mapping Incomplete", "Select a SCIM group and resource.")
            return

        def action() -> None:
            payload = {
                "scim_group_id": str(scim_group_id),
                "resource_id": int(resource_id),
                "active": self.admin_scim_mapping_active_input.isChecked(),
            }
            if mapping_id is None:
                self.api_client.create_scim_mapping(**payload)
            else:
                self.api_client.update_scim_mapping(mapping_id, **payload)
            self.refresh_admin_scim()

        guarded(self, "SCIM Mapping Save Failed", action)

    def on_admin_scim_group_selected(self) -> None:
        row = self.admin_scim_groups_table.currentRow()
        if row < 0:
            return
        item = self.admin_scim_groups_table.item(row, 0)
        if item is None:
            return
        scim_group_id = item.text()
        for index in range(self.admin_scim_group_box.count()):
            if self.admin_scim_group_box.itemData(index) == scim_group_id:
                self.admin_scim_group_box.setCurrentIndex(index)
                break

    def on_admin_scim_mapping_selected(self) -> None:
        mapping_id = selected_row_id(self.admin_scim_mappings_table)
        if mapping_id is None:
            return
        row = self.admin_scim_mapping_rows_by_id.get(mapping_id, {})
        self.admin_scim_mapping_active_input.setChecked(bool(row.get("active", True)))
        if row.get("resource_id"):
            bind_combo(self.admin_scim_mapping_resource_box, self.resources_by_id.values(), self._resource_label_with_system, current=row.get("resource_id"))

    def refresh_admin_endpoint(self) -> None:
        if not self.api_client or not self._is_admin():
            return
        _, path, _ = self._admin_selection()
        self.admin_path_input.setText(path)

        def action() -> None:
            payload = self.api_client.get_path(path)
            rows = self._rows_from_payload(payload)
            self.admin_rows_by_id = {
                int(row["id"]): row for row in rows if isinstance(row.get("id"), int) or str(row.get("id", "")).isdigit()
            }
            populate_table(self.admin_table, rows, self._columns_for_rows(rows), id_key="id")
            self.admin_status_label.setText(f"Loaded {len(rows)} row(s) from {path}.")

        guarded(self, "Admin Refresh Failed", action)

    def load_admin_template(self) -> None:
        _, path, template = self._admin_selection()
        self.admin_path_input.setText(path)
        self.admin_payload_input.setPlainText(json.dumps(template or {}, indent=2, default=str))

    def on_admin_row_selected(self) -> None:
        row_id = selected_row_id(self.admin_table)
        if row_id is None:
            return
        self.admin_id_input.setText(str(row_id))
        row = self.admin_rows_by_id.get(row_id)
        if row:
            self.admin_payload_input.setPlainText(json.dumps({key: value for key, value in row.items() if key != "id"}, indent=2, default=str))

    def admin_create(self) -> None:
        self._admin_mutation("POST", self.admin_path_input.text().strip(), include_id=False)

    def admin_update(self) -> None:
        self._admin_mutation("PUT", self._admin_item_path(), include_id=True)

    def admin_delete(self) -> None:
        self._admin_mutation("DELETE", self._admin_item_path(), include_id=True)

    def admin_post_action(self) -> None:
        self._admin_mutation("POST", self.admin_path_input.text().strip(), include_id=False)

    def _admin_mutation(self, method: str, path: str, *, include_id: bool) -> None:
        if not self.api_client or not self._is_admin():
            return
        if include_id and not self._admin_id():
            QMessageBox.warning(self, "No Row Selected", "Select a row or enter an ID first.")
            return

        def action() -> None:
            payload = json.loads(self.admin_payload_input.toPlainText() or "{}")
            if method == "POST":
                result = self.api_client.post_path(path, payload)
            elif method == "PUT":
                result = self.api_client.put_path(path, payload)
            elif method == "DELETE":
                result = self.api_client.delete_path(path)
            else:
                raise ValueError(f"Unsupported admin method {method}.")
            self.admin_status_label.setText(f"{method} {path} completed.")
            if result is not None and method != "DELETE":
                self.admin_payload_input.setPlainText(json.dumps(result, indent=2, default=str))
            self.refresh_admin_endpoint()

        guarded(self, "Admin Action Failed", action)

    def _admin_selection(self) -> tuple[str, str, dict[str, Any] | None]:
        label = self.admin_endpoint_box.currentText()
        _, path, template = ADMIN_ENDPOINTS[label]
        return label, path, template

    def _admin_item_path(self) -> str:
        path = self.admin_path_input.text().strip().rstrip("/")
        item_id = self._admin_id()
        return f"{path}/{item_id}" if item_id else path

    def _admin_id(self) -> str:
        return self.admin_id_input.text().strip() or str(selected_row_id(self.admin_table) or "")

    def _rows_from_payload(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("Resources"), list):
            return [self._flatten_row(item) for item in payload["Resources"] if isinstance(item, dict)]
        if isinstance(payload, list):
            return [self._flatten_row(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            return [self._flatten_row(payload)]
        return [{"value": payload}]

    def _columns_for_rows(self, rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
        if not rows:
            return [("ID", "id"), ("Value", "value")]
        keys = list(rows[0].keys())
        if "id" in keys:
            keys.remove("id")
            keys.insert(0, "id")
        return [(key.replace("_", " ").title(), key) for key in keys[:8]]

    def _flatten_row(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: json.dumps(value, default=str) if isinstance(value, (dict, list)) else value
            for key, value in row.items()
        }

    def _update_action_buttons(self) -> None:
        can_decide = "approvals.decide" in self.current_permissions and selected_row_id(self.approvals_table) is not None
        self.approve_button.setEnabled(can_decide)
        self.reject_button.setEnabled(can_decide)
        self.submit_request_button.setEnabled("requests.write" in self.current_permissions and self.resource_box.count() > 0)
        self.create_delegation_button.setEnabled("delegations.write" in self.current_permissions and self.delegate_box.count() > 0)

    def _is_admin(self) -> bool:
        return "admin.dashboard" in self.current_permissions

    def _resource_label(self, resource: dict[str, Any]) -> str:
        return f"{resource['name']} ({resource.get('description') or 'resource'})"

    def _resource_label_with_system(self, resource: dict[str, Any]) -> str:
        return f"{resource['name']} | {self._system_name(int(resource['system_id']))}"

    def _resource_name(self, resource_id: int) -> str:
        resource = self.resources_by_id.get(resource_id)
        return str(resource["name"]) if resource else f"Resource {resource_id}"

    def _system_name(self, system_id: int) -> str:
        system = self.systems_by_id.get(system_id)
        return str(system["name"]) if system else f"System {system_id}"

    def _identity_name(self, identity_id: int) -> str:
        if self.current_identity and int(self.current_identity["id"]) == identity_id:
            return str(self.current_identity["full_name"])
        identity = self.identities_by_id.get(identity_id)
        return str(identity["full_name"]) if identity else f"Identity {identity_id}"


def modules_for_permissions(permissions: list[str]) -> list[str]:
    module_map = {
        "requests.write": "Request Access",
        "assignments.read": "My Access",
        "requests.read": "My Requests",
        "approvals.read": "My Approvals",
        "delegations.read": "Delegations",
        "admin.dashboard": "Admin Dashboard",
        "provisioning.read": "Provisioning Queue",
        "audit.read": "Audit",
    }
    return [label for permission, label in module_map.items() if permission in permissions]


def main() -> None:
    app = QApplication(sys.argv)
    window = ClientWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
