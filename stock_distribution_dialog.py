from typing import Dict, List, Optional

import pandas as pd
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models import PandasTableModel
from styles import get_dialog_styles


def normalize_category(cat: str) -> str:
    if not cat or cat == "Без категории":
        return ""
    # Замена русских букв на латинские (только те, что могут встретиться)
    mapping = str.maketrans({'А': 'A', 'В': 'B', 'С': 'C'})
    return cat.upper().translate(mapping)


class StockDistributionDialog(QDialog):
    def __init__(self, parent=None, model: Optional[PandasTableModel] = None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Распределение остатков по категориям")
        self.resize(700, 500)
        self.setStyleSheet(get_dialog_styles())

        # Основной layout
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Верхняя панель с чекбоксом
        top_layout = QHBoxLayout()
        self.include_order_check = QCheckBox("Учитывать сделанный заказ")
        self.include_order_check.setToolTip(
            "Если отмечено, к остатку прибавляется значение из колонки 'Заказ'.\n"
            "Показывает потенциальный остаток после поступления заказа."
        )
        top_layout.addWidget(self.include_order_check)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        # Таблица для вывода данных
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Категория",
            "Остаток (шт)",
            "% от общего (шт)",
            "Остаток (руб)",
            "% от общего (руб)"
        ])
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)

        # Скрыть нумерацию строк
        self.table.verticalHeader().setVisible(False)

        # Фиксированная ширина колонок (устанавливается один раз)
        self.table.setColumnWidth(0, 200)   # Категория
        self.table.setColumnWidth(1, 100)   # Остаток (шт)
        self.table.setColumnWidth(2, 80)    # % от общего (шт)
        self.table.setColumnWidth(3, 150)   # Остаток (руб)
        self.table.setColumnWidth(4, 80)    # % от общего (руб)

        layout.addWidget(self.table)

        # Кнопка закрытия внизу
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

        # Автоматическое обновление при изменении чекбокса
        self.include_order_check.stateChanged.connect(self.update_data)

        # Первоначальная загрузка данных
        self.update_data()

    def update_data(self) -> None:
        """Обновляет данные в таблице на основе текущего фильтра и состояния чекбокса."""
        if self.model is None:
            self._show_no_data("Модель данных не задана.")
            return

        # Получаем список отфильтрованных кодов
        filtered_codes = self.model.get_filtered_codes()
        if not filtered_codes:
            self._show_no_data("Нет отображаемых товаров.")
            return

        # Получаем исходный DataFrame
        df = self.model.get_original_df()
        if df.empty or 'Код' not in df.columns:
            self._show_no_data("Нет данных для анализа.")
            return

        # Создаём словарь для быстрого доступа к строке по коду
        code_to_row = {}
        for idx, row in df.iterrows():
            code = str(row['Код'])
            if code not in code_to_row:
                code_to_row[code] = row

        # Словарь для накопления статистики по категориям: категория -> [сумма_шт, сумма_руб]
        cat_stats: Dict[str, List[float]] = {}

        # Получаем пользовательские заказы (если учитываем)
        user_orders = self.model.get_user_orders() if self.include_order_check.isChecked() else {}

        for code in filtered_codes:
            if code not in code_to_row:
                continue
            row = code_to_row[code]

            # Извлекаем категорию
            category = row.get('Категория товара', None)
            if pd.isna(category) or category == "":
                category = "Без категории"
            else:
                category = str(category).strip()

            # Извлекаем конечный остаток и цену
            try:
                end_stock = float(row.get('Конечный остаток', 0))
            except (ValueError, TypeError):
                end_stock = 0.0

            try:
                price = float(row.get('Цена', 0))
            except (ValueError, TypeError):
                price = 0.0

            # Определяем остаток с учётом заказа или без
            stock = end_stock
            if self.include_order_check.isChecked():
                order = user_orders.get(code, row.get('Заказ', 0))
                try:
                    order = float(order)
                except (ValueError, TypeError):
                    order = 0.0
                stock += order

            # Если остаток положительный, добавляем в статистику
            if stock > 0:
                if category not in cat_stats:
                    cat_stats[category] = [0.0, 0.0]
                cat_stats[category][0] += stock
                cat_stats[category][1] += stock * price

        if not cat_stats:
            self._show_no_data("Нет позиций с положительным остатком.")
            return

        # Вычисляем общие итоги
        total_qty = sum(v[0] for v in cat_stats.values())
        total_amount = sum(v[1] for v in cat_stats.values())

        # Подготавливаем данные для таблицы
        data = [(cat, stats[0], stats[1]) for cat, stats in cat_stats.items()]

        # Сортировка с приоритетным порядком категорий
        priority_order = ["AA", "AB", "BA", "BB", "AC", "CA", "CB", "BC", "CC"]

        def sort_key(item):
            cat, qty, amount = item
            norm = normalize_category(cat)
            if cat == "Без категории":
                return (len(priority_order) + 1, "")
            if norm in priority_order:
                idx = priority_order.index(norm)
                return (idx, norm)
            else:
                return (len(priority_order), norm)

        data.sort(key=sort_key)

        # Очищаем таблицу и устанавливаем количество строк
        self.table.setRowCount(0)
        self.table.setRowCount(len(data) + 1)  # +1 для итоговой строки

        # Заполняем таблицу
        for row_idx, (cat, qty, amount) in enumerate(data):
            # Категория
            self._set_item(row_idx, 0, cat, bold=False)

            # Остаток (шт)
            qty_str = f"{int(round(qty)):,}".replace(',', ' ')
            self._set_item(row_idx, 1, qty_str, align_right=True)

            # % от общего (шт)
            qty_percent = (qty / total_qty * 100) if total_qty > 0 else 0
            self._set_item(row_idx, 2, f"{qty_percent:.1f}%", align_right=True)

            # Остаток (руб)
            amount_str = f"{amount:,.2f}".replace(',', ' ').replace('.', ',')
            self._set_item(row_idx, 3, amount_str, align_right=True)

            # % от общего (руб)
            amount_percent = (amount / total_amount * 100) if total_amount > 0 else 0
            self._set_item(row_idx, 4, f"{amount_percent:.1f}%", align_right=True)

        # Итоговая строка
        last_row = len(data)
        self._set_item(last_row, 0, "ИТОГО", bold=True)

        total_qty_str = f"{int(round(total_qty)):,}".replace(',', ' ')
        self._set_item(last_row, 1, total_qty_str, align_right=True, bold=True)

        self._set_item(last_row, 2, "100.0%", align_right=True, bold=True)

        total_amount_str = f"{total_amount:,.2f}".replace(',', ' ').replace('.', ',')
        self._set_item(last_row, 3, total_amount_str, align_right=True, bold=True)

        self._set_item(last_row, 4, "100.0%", align_right=True, bold=True)

    def _set_item(self, row: int, col: int, text: str,
                  align_right: bool = False, bold: bool = False) -> None:
        """Устанавливает ячейку таблицы с заданным форматированием."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        if align_right:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        else:
            item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        if bold:
            font = QFont()
            font.setBold(True)
            item.setFont(font)

        self.table.setItem(row, col, item)

    def _show_no_data(self, message: str) -> None:
        """Очищает таблицу и показывает сообщение в одной ячейке."""
        self.table.setRowCount(1)
        self.table.setColumnCount(1)
        item = QTableWidgetItem(message)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(0, 0, item)
        self.table.horizontalHeader().setVisible(False)
        QMessageBox.information(self, "Информация", message)