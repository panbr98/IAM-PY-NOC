from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


APP_QSS = """
QMainWindow, QWidget {
    background: #f6f8fb;
    color: #1f2937;
    font-size: 13px;
}
QLabel#pageTitle {
    color: #111827;
    font-size: 20px;
    font-weight: 700;
}
QLabel#sectionTitle {
    color: #111827;
    font-size: 15px;
    font-weight: 700;
}
QLabel#muted {
    color: #6b7280;
}
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
    background: #ffffff;
    border: 1px solid #d7dde8;
    border-radius: 6px;
    padding: 7px 9px;
    min-height: 24px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus {
    border: 1px solid #2563eb;
}
QPushButton {
    background: #ffffff;
    border: 1px solid #cfd6e3;
    border-radius: 6px;
    color: #1f2937;
    font-weight: 600;
    padding: 8px 12px;
}
QPushButton:hover {
    background: #eef4ff;
    border-color: #8fb4ff;
}
QPushButton:pressed {
    background: #dbeafe;
}
QPushButton[primary="true"] {
    background: #1d4ed8;
    border-color: #1d4ed8;
    color: #ffffff;
}
QPushButton[danger="true"] {
    background: #b91c1c;
    border-color: #b91c1c;
    color: #ffffff;
}
QListWidget#sidebar {
    background: #101827;
    border: 0;
    color: #dbe4f0;
    font-weight: 600;
    outline: 0;
}
QListWidget#sidebar::item {
    border-radius: 6px;
    margin: 3px 8px;
    padding: 10px 12px;
}
QListWidget#sidebar::item:selected {
    background: #2563eb;
    color: #ffffff;
}
QTabWidget::pane {
    border: 1px solid #dce2ec;
    border-radius: 7px;
    background: #ffffff;
}
QTabBar::tab {
    background: #edf1f7;
    border: 1px solid #dce2ec;
    border-bottom: 0;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 12px;
    margin-right: 3px;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #1d4ed8;
}
QTableWidget {
    background: #ffffff;
    border: 1px solid #dce2ec;
    border-radius: 7px;
    gridline-color: #edf1f7;
    selection-background-color: #dbeafe;
    selection-color: #111827;
}
QHeaderView::section {
    background: #f1f5f9;
    border: 0;
    border-right: 1px solid #dce2ec;
    color: #475569;
    font-weight: 700;
    padding: 8px;
}
QFrame#card {
    background: #ffffff;
    border: 1px solid #dce2ec;
    border-radius: 8px;
}
"""


def apply_app_theme(app: QApplication) -> None:
    app.setStyleSheet(APP_QSS)


def make_card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 14, 14, 14)
    layout.setSpacing(10)
    if title:
        label = QLabel(title)
        label.setObjectName("sectionTitle")
        layout.addWidget(label)
    return card, layout


def set_banner(label: QLabel, message: str, *, ok: bool = True) -> None:
    label.setText(message)
    color = "#166534" if ok else "#991b1b"
    border = "#bbf7d0" if ok else "#fecaca"
    background = "#f0fdf4" if ok else "#fef2f2"
    label.setStyleSheet(f"padding: 10px 12px; border-radius: 7px; border: 1px solid {border}; background: {background}; color: {color};")
    label.setWordWrap(True)


def guarded(parent: QWidget, title: str, action: Callable[[], Any]) -> Any:
    try:
        return action()
    except Exception as exc:
        QMessageBox.critical(parent, title, str(exc))
        return None


def populate_table(
    table: QTableWidget,
    rows: Iterable[dict[str, Any]],
    columns: list[tuple[str, str]],
    *,
    id_key: str = "id",
) -> None:
    materialized = list(rows)
    table.setSortingEnabled(False)
    table.clear()
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels([label for label, _ in columns])
    table.setRowCount(len(materialized))
    for row_index, row in enumerate(materialized):
        for column_index, (_, key) in enumerate(columns):
            value = row.get(key, "")
            text = "" if value is None else str(value)
            item = QTableWidgetItem(text)
            if column_index == 0:
                item.setData(Qt.UserRole, row.get(id_key))
            table.setItem(row_index, column_index, item)
    table.setSortingEnabled(True)
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    table.resizeColumnsToContents()


def selected_row_id(table: QTableWidget) -> int | None:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    if item is None:
        return None
    value = item.data(Qt.UserRole)
    return int(value) if value is not None else None


def selected_row_payload(table: QTableWidget, rows_by_id: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    row_id = selected_row_id(table)
    if row_id is None:
        return None
    return rows_by_id.get(row_id)


def bind_combo(
    combo: QComboBox,
    rows: Iterable[dict[str, Any]],
    labeler: Callable[[dict[str, Any]], str],
    *,
    include_none: bool = False,
    none_label: str = "None",
    current: Any = None,
) -> None:
    combo.blockSignals(True)
    combo.clear()
    if include_none:
        combo.addItem(none_label, None)
    for row in rows:
        combo.addItem(labeler(row), row.get("id"))
    if current is not None:
        for index in range(combo.count()):
            if combo.itemData(index) == current:
                combo.setCurrentIndex(index)
                break
    combo.blockSignals(False)
