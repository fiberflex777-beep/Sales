# customer_analysis_dialog.py
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QLabel,
    QLineEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from styles import get_dialog_styles


class CustomerAnalysisDialog(QDialog):
    """Диалог анализа покупателей: сводная таблица по контрагентам."""

    def __init__(self, parent=None,
                 movement_details: Optional[Dict[str, List[Dict]]] = None,
                 price_by_code: Optional[Dict[str, float]] = None,
                 filtered_codes: Optional[List[str]] = None):
        super().__init__(parent)
        self.movement_details = movement_details or {}
        self.price_by_code = price_by_code or {}
        self.filtered_codes_set = set(filtered_codes) if filtered_codes else None
        self.setWindowTitle("Анализ покупателей")
        self.resize(800, 600)
        self.setStyleSheet(get_dialog_styles())

        # Данные для сортировки
        self.stats = []          # полный список кортежей (name, qty, amount)
        self.filtered_stats = [] # отфильтрованный список
        self.current_sort_column = 2      # по умолчанию сортируем по сумме
        self.current_sort_order = Qt.SortOrder.DescendingOrder  # по убыванию

        layout = QVBoxLayout()
        self.setLayout(layout)

        # ---- Поле поиска ----
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите часть наименования контрагента...")
        self.search_edit.textChanged.connect(self.apply_filter)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Таблица с тремя колонками
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels([
            "Контрагент",
            "Количество (шт)",
            "Сумма (руб)"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)  # отключаем встроенную сортировку
        self.table.verticalHeader().setVisible(False)

        # Настройка ширины колонок
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 150)

        # Подключаем обработчик кликов по заголовку для ручной сортировки
        header.sectionClicked.connect(self.on_header_clicked)

        layout.addWidget(self.table)

        # ----- Панель итогов под таблицей -----
        summary_layout = QHBoxLayout()

        self.total_label = QLabel("Итого:")
        self.total_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.total_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(self.total_label)

        summary_layout.addStretch()

        self.total_qty_label = QLabel("0")
        self.total_qty_label.setFixedWidth(150)
        self.total_qty_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_qty_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(self.total_qty_label)

        self.total_amount_label = QLabel("0,00")
        self.total_amount_label.setFixedWidth(150)
        self.total_amount_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.total_amount_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(self.total_amount_label)

        layout.addLayout(summary_layout)

        # Кнопка закрытия
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.populate_table()

    def populate_table(self):
        """Сбор и агрегация данных по контрагентам с учётом фильтра по кодам."""
        # Словарь для агрегации: контрагент -> [суммарное_количество, суммарная_стоимость]
        temp_stats = {}

        for code, movements in self.movement_details.items():
            # Если задан фильтр по кодам и текущий код не входит в него — пропускаем
            if self.filtered_codes_set and code not in self.filtered_codes_set:
                continue

            price = self.price_by_code.get(code, 0.0)
            for mov in movements:
                outgoing = mov.get('outgoing', 0.0)
                if outgoing <= 0:
                    continue
                counterparty = mov.get('counterparty', '').strip()
                if not counterparty:
                    counterparty = "Без контрагента"

                if counterparty not in temp_stats:
                    temp_stats[counterparty] = [0.0, 0.0]
                temp_stats[counterparty][0] += outgoing
                temp_stats[counterparty][1] += outgoing * price

        if not temp_stats:
            QMessageBox.information(self, "Информация", "Нет данных о покупателях.")
            self.table.setRowCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("Нет данных"))
            self.total_qty_label.setText("0")
            self.total_amount_label.setText("0,00")
            return

        # Преобразуем в список кортежей для удобства сортировки
        self.stats = [(name, qty, amt) for name, (qty, amt) in temp_stats.items()]

        # Применяем фильтр (если текст уже есть)
        self.apply_filter()

    def apply_filter(self):
        """Фильтрует stats по тексту из поля поиска и обновляет таблицу."""
        filter_text = self.search_edit.text().strip().lower()

        if not filter_text:
            self.filtered_stats = self.stats.copy()
        else:
            self.filtered_stats = [
                row for row in self.stats
                if filter_text in row[0].lower()
            ]

        # Сортируем отфильтрованный список согласно текущим настройкам
        self.sort_filtered_stats()

        # Обновляем таблицу
        self.refresh_table()

    def sort_filtered_stats(self):
        """Сортирует self.filtered_stats по текущим параметрам."""
        if self.current_sort_column == 0:
            self.filtered_stats.sort(key=lambda x: x[0], reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))
        elif self.current_sort_column == 1:
            self.filtered_stats.sort(key=lambda x: x[1], reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))
        else:  # column == 2
            self.filtered_stats.sort(key=lambda x: x[2], reverse=(self.current_sort_order == Qt.SortOrder.DescendingOrder))

    def sort_stats(self):
        """Сортирует полный stats (оставлено для обратной совместимости, но сейчас не используется напрямую)."""
        pass

    def refresh_table(self):
        """Заполняет таблицу данными из self.filtered_stats и обновляет итоги."""
        self.table.setRowCount(len(self.filtered_stats))
        total_qty = 0.0
        total_amt = 0.0

        for row, (name, qty, amt) in enumerate(self.filtered_stats):
            # Контрагент
            self._set_item(row, 0, name, align_left=True)

            # Количество (целое число)
            qty_int = int(qty)
            qty_str = f"{qty_int:,}".replace(',', ' ')
            self._set_item(row, 1, qty_str, align_right=True)

            # Сумма (с двумя знаками после запятой)
            amt_str = f"{amt:,.2f}".replace(',', ' ').replace('.', ',')
            self._set_item(row, 2, amt_str, align_right=True)

            total_qty += qty
            total_amt += amt

        # Итоги
        total_qty_str = f"{int(total_qty):,}".replace(',', ' ')
        total_amt_str = f"{total_amt:,.2f}".replace(',', ' ').replace('.', ',')
        self.total_qty_label.setText(total_qty_str)
        self.total_amount_label.setText(total_amt_str)

    def on_header_clicked(self, logical_index: int):
        """Обработчик клика по заголовку колонки."""
        # Если кликнули по той же колонке, меняем порядок сортировки
        if logical_index == self.current_sort_column:
            self.current_sort_order = Qt.SortOrder.DescendingOrder if self.current_sort_order == Qt.SortOrder.AscendingOrder else Qt.SortOrder.AscendingOrder
        else:
            self.current_sort_column = logical_index
            self.current_sort_order = Qt.SortOrder.DescendingOrder  # по умолчанию убывание

        # Применяем сортировку к отфильтрованным данным
        self.sort_filtered_stats()
        self.refresh_table()

    def _set_item(self, row: int, col: int, text: str,
                  align_left: bool = False, align_right: bool = False,
                  bold: bool = False) -> None:
        """Устанавливает ячейку таблицы с заданным форматированием."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if align_left:
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif align_right:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        if bold:
            font = QFont()
            font.setBold(True)
            item.setFont(font)

        self.table.setItem(row, col, item)