from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox, QTableWidget, QTableWidgetItem, QWidget


def set_banner(label: QLabel, message: str, *, ok: bool = True) -> None:
    label.setText(message)
    color = "#176b42" if ok else "#9f2d20"
    background = "#e9f7ef" if ok else "#fdecea"
    label.setStyleSheet(f"padding: 8px; border: 1px solid {color}; background: {background}; color: {color};")
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
