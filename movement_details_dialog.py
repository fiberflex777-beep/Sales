# movement_details_dialog.py
from datetime import datetime
from typing import List, Dict, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from styles import get_dialog_styles


class MovementDetailsDialog(QDialog):
    """Диалог отображения детальной информации о движениях товара."""

    def __init__(self, parent=None, code: str = "", initial_stock: float = 0.0,
                 price: float = 0.0, movements: Optional[List[Dict]] = None):
        super().__init__(parent)
        self.code = code
        self.initial_stock = initial_stock
        self.price = price
        self.movements = movements or []
        self.setWindowTitle(f"Движения товара: {code}")
        self.resize(1300, 600)
        self.setStyleSheet(get_dialog_styles())

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Таблица
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Дата", "Документ", "Контрагент",
            "Начальный ост.", "Приход", "Расход",
            "Конечный ост.", "Цена"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for i in (0, 3, 4, 5, 6, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(3, 85)
        self.table.setColumnWidth(4, 85)
        self.table.setColumnWidth(5, 85)
        self.table.setColumnWidth(6, 85)
        self.table.setColumnWidth(7, 85)

        layout.addWidget(self.table)

        # ----- Панель итогов под колонками -----
        self.summary_layout = QHBoxLayout()

        # Метка количества строк
        self.selected_rows_label = QLabel("Строк: 0")
        self.selected_rows_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        # Жирным сделаем только цифру через HTML (см. update)
        self.selected_rows_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_layout.addWidget(self.selected_rows_label)

        self.summary_layout.addStretch()

        # Метки для числовых колонок с фиксированной шириной
        self.sum_start_label = QLabel()
        self.sum_start_label.setFixedWidth(85)
        self.sum_start_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sum_start_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_layout.addWidget(self.sum_start_label)

        self.sum_incoming_label = QLabel()
        self.sum_incoming_label.setFixedWidth(85)
        self.sum_incoming_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sum_incoming_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_layout.addWidget(self.sum_incoming_label)

        self.sum_outgoing_label = QLabel()
        self.sum_outgoing_label.setFixedWidth(85)
        self.sum_outgoing_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sum_outgoing_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_layout.addWidget(self.sum_outgoing_label)

        self.sum_end_label = QLabel()
        self.sum_end_label.setFixedWidth(85)
        self.sum_end_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sum_end_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_layout.addWidget(self.sum_end_label)

        self.sum_price_label = QLabel()
        self.sum_price_label.setFixedWidth(85)
        self.sum_price_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sum_price_label.setTextFormat(Qt.TextFormat.RichText)
        self.summary_layout.addWidget(self.sum_price_label)

        layout.addLayout(self.summary_layout)

        # Кнопка закрытия
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        self.table.selectionModel().selectionChanged.connect(self.update_selection_summary)
        self.populate_table()

    def populate_table(self):
        if not self.movements:
            QMessageBox.information(self, "Информация", "Нет данных для отображения.")
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Нет движений"))
            self.update_selection_summary()
            return

        sorted_movements = sorted(self.movements, key=lambda x: x['date'])
        running_stock = self.initial_stock
        rows_data = []

        for mov in sorted_movements:
            date = mov['date']
            doc_full = mov.get('doc_full', mov.get('doc_type', ''))
            counterparty = mov['counterparty']
            incoming = mov.get('incoming', 0.0)
            outgoing = mov.get('outgoing', 0.0)

            start_stock = running_stock
            end_stock = running_stock + incoming - outgoing

            rows_data.append({
                'date': date,
                'doc_full': doc_full,
                'counterparty': counterparty,
                'start_stock': start_stock,
                'incoming': incoming,
                'outgoing': outgoing,
                'end_stock': end_stock,
                'price': self.price
            })

            running_stock = end_stock

        self.table.setRowCount(len(rows_data))

        for row_idx, row in enumerate(rows_data):
            date_str = row['date'].strftime('%d.%m.%Y') if isinstance(row['date'], datetime) else str(row['date'])
            self._set_item(row_idx, 0, date_str, align_center=True)
            self._set_item(row_idx, 1, row['doc_full'], align_left=True)
            self._set_item(row_idx, 2, row['counterparty'], align_left=True)
            self._set_item(row_idx, 3, f"{row['start_stock']:.0f}".replace('.', ','), align_center=True)
            self._set_item(row_idx, 4, f"{row['incoming']:.0f}".replace('.', ','), align_center=True)
            self._set_item(row_idx, 5, f"{row['outgoing']:.0f}".replace('.', ','), align_center=True)
            self._set_item(row_idx, 6, f"{row['end_stock']:.0f}".replace('.', ','), align_center=True)
            price_str = f"{row['price']:.2f}".replace('.', ',')
            self._set_item(row_idx, 7, price_str, align_center=True)

        self.table.resizeColumnToContents(2)
        self.update_selection_summary()

    def _set_item(self, row, col, text, align_left=False, align_right=False, align_center=False, bold=False):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if align_left:
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif align_right:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        elif align_center:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if bold:
            font = QFont()
            font.setBold(True)
            item.setFont(font)

        self.table.setItem(row, col, item)

    def update_selection_summary(self):
        indexes = self.table.selectionModel().selectedIndexes()
        if not indexes:
            self.selected_rows_label.setText("Строк: 0")
            self.sum_start_label.setText("<b>0</b>")
            self.sum_incoming_label.setText("<b>0</b>")
            self.sum_outgoing_label.setText("<b>0</b>")
            self.sum_end_label.setText("<b>0</b>")
            self.sum_price_label.setText("<b>0</b>")
            return

        rows = set()
        sums = {3: 0.0, 4: 0.0, 5: 0.0, 6: 0.0, 7: 0.0}

        for idx in indexes:
            row = idx.row()
            col = idx.column()
            rows.add(row)
            if col in sums:
                item = self.table.item(row, col)
                if item and item.text():
                    clean_text = item.text().replace(' ', '').replace(',', '.')
                    try:
                        value = float(clean_text)
                    except ValueError:
                        value = 0.0
                    sums[col] += value

        # Количество строк с HTML жирным
        self.selected_rows_label.setText(f"Строк: <b>{len(rows)}</b>")

        # Форматирование чисел с разделителями тысяч
        def format_int(val):
            return f"{int(val):,}".replace(',', ' ')

        self.sum_start_label.setText(f"<b>{format_int(sums[3])}</b>")
        self.sum_incoming_label.setText(f"<b>{format_int(sums[4])}</b>")
        self.sum_outgoing_label.setText(f"<b>{format_int(sums[5])}</b>")
        self.sum_end_label.setText(f"<b>{format_int(sums[6])}</b>")

        price_str = f"{sums[7]:,.2f}".replace(',', ' ').replace('.', ',')
        self.sum_price_label.setText(f"<b>{price_str}</b>")