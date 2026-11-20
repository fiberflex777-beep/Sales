# stock_value_analysis_dialog.py
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt          # <-- добавлено
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from plot_utils import create_empty_graph_message
from styles import get_dialog_styles


class StockValueAnalysisDialog(QDialog):
    """Диалог с графиком суммарной стоимости остатков (в рублях) по дням."""

    def __init__(self, parent=None,
                 movement_data: Optional[Dict[str, List]] = None,
                 filtered_codes: Optional[List[str]] = None,
                 price_by_code: Optional[Dict[str, float]] = None,
                 initial_stock_by_code: Optional[Dict[str, float]] = None,
                 period_text: str = ""):
        super().__init__(parent)
        self.movement_data = movement_data or {}
        self.filtered_codes_set = set(filtered_codes) if filtered_codes else None
        self.price_by_code = price_by_code or {}
        self.initial_stock_by_code = initial_stock_by_code or {}
        self.period_text = period_text

        self.setWindowTitle("Анализ остатков в деньгах")
        self.resize(1200, 600)
        self.setStyleSheet(get_dialog_styles())

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.placeholder_label = QLabel("Загрузка графика...")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.placeholder_label)

        self.figure = None
        self.canvas = None

        self.calculate_and_plot()

    def calculate_and_plot(self):
        """Расчёт временного ряда суммарной стоимости остатков и построение графика."""
        # 1. Определяем период из period_text
        start_date, end_date = self._parse_period(self.period_text)
        if start_date is None or end_date is None:
            self._show_error("Не удалось определить период анализа.")
            return

        # 2. Фильтруем коды
        codes_to_process = set(self.movement_data.keys())
        if self.filtered_codes_set is not None:
            codes_to_process &= self.filtered_codes_set

        if not codes_to_process:
            self._show_error("Нет товаров для анализа (проверьте фильтр).")
            return

        # 3. Создаём словарь изменений стоимости по дням для каждого товара
        # Для каждого дня будем хранить изменение стоимости (руб) = (incoming - outgoing) * price
        daily_value_changes = {}  # date -> float

        for code in codes_to_process:
            price = self.price_by_code.get(code, 0.0)
            if price == 0.0:
                continue  # товары с нулевой ценой не влияют на стоимость
            movements = self.movement_data.get(code, [])
            for date, incoming, outgoing in movements:
                if start_date <= date <= end_date:
                    change = (incoming - outgoing) * price
                    daily_value_changes[date] = daily_value_changes.get(date, 0.0) + change

        # 4. Вычисляем начальную суммарную стоимость
        total_initial_value = 0.0
        for code in codes_to_process:
            init_stock = self.initial_stock_by_code.get(code, 0.0)
            price = self.price_by_code.get(code, 0.0)
            total_initial_value += init_stock * price

        # 5. Генерируем последовательность дат и считаем накопленную стоимость
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        dates = date_range.date
        value_series = []
        current_value = total_initial_value

        for date in dates:
            if date in daily_value_changes:
                current_value += daily_value_changes[date]
            value_series.append(current_value)

        # 6. Построение графика
        self._plot_stock_value(dates, value_series, start_date, end_date)

    def _parse_period(self, period_text: str):
        """Парсит строку периода вида 'DD.MM.YYYY - DD.MM.YYYY'."""
        import re
        pattern = r'(\d{2}\.\d{2}\.\d{4})\s*-\s*(\d{2}\.\d{2}\.\d{4})'
        match = re.search(pattern, period_text)
        if not match:
            return None, None
        start_str, end_str = match.groups()
        try:
            start_date = datetime.strptime(start_str, '%d.%m.%Y').date()
            end_date = datetime.strptime(end_str, '%d.%m.%Y').date()
            return start_date, end_date
        except ValueError:
            return None, None

    def _plot_stock_value(self, dates, values, start_date, end_date):
        """Строит график с использованием matplotlib (аналогично PlotManager)."""
        # Удаляем placeholder
        layout = self.layout()
        layout.removeWidget(self.placeholder_label)
        self.placeholder_label.deleteLater()
        self.placeholder_label = None

        # Создаём фигуру
        self.figure = Figure(figsize=(12, 6), facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

        ax = self.figure.add_subplot(111)

        # Настройка стиля
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#dddddd')
        ax.spines['left'].set_color('#dddddd')
        ax.tick_params(colors='#666666', labelsize=9)
        ax.grid(True, linestyle='--', alpha=0.3, linewidth=0.5)
        ax.set_axisbelow(True)

        # Преобразование дат для matplotlib
        mpl_dates = mdates.date2num(dates)

        # Линия и заливка
        line_color = '#3399ff'
        ax.plot(mpl_dates, values, color=line_color, linewidth=1.5, label='Стоимость остатка')
        ax.fill_between(mpl_dates, values, 0, color=line_color, alpha=0.4)

        ax.set_xlim(mpl_dates[0], mpl_dates[-1])
        ax.margins(x=0)
        ax.set_ylim(bottom=0)

        # Добавляем маркеры месяцев/годов (как в PlotManager)
        self._add_month_year_markers(ax, start_date, end_date)

        ax.set_ylabel('Стоимость остатка (руб)', fontsize=10)
        ax.set_title('Суммарная стоимость остатков по дням', fontsize=14, fontweight='bold')

        # Форматирование подписей оси Y как денег
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:,.0f}'.replace(',', ' ')))

        self.figure.tight_layout()
        self.canvas.draw()

    def _add_month_year_markers(self, ax, start_date, end_date):
        """Копия метода из PlotManager для добавления вертикальных линий и подписей."""
        import matplotlib.pyplot as plt

        max_y = ax.get_ylim()[1]
        min_y = ax.get_ylim()[0]
        y_range = max_y - min_y if max_y != min_y else 1
        y_pos_months = max_y + y_range * 0.08
        y_pos_years = min_y - y_range * 0.04

        month_boundaries = []
        year_change_boundaries = []

        current_date = start_date.replace(day=1)
        prev_year = None

        month_names = {
            1: 'Янв.', 2: 'Фев.', 3: 'Март', 4: 'Апр.', 5: 'Май', 6: 'Июнь',
            7: 'Июль', 8: 'Авг.', 9: 'Сент.', 10: 'Окт.', 11: 'Ноя.', 12: 'Дек.'
        }

        while current_date <= end_date:
            if current_date.day == 1:
                month_boundaries.append(current_date)
                if prev_year is not None and current_date.year != prev_year:
                    year_change_boundaries.append(current_date)
                prev_year = current_date.year

            if current_date.month == 12:
                current_date = current_date.replace(year=current_date.year + 1, month=1, day=1)
            else:
                current_date = current_date.replace(month=current_date.month + 1, day=1)

        if end_date.month == 12:
            next_month_boundary = end_date.replace(year=end_date.year + 1, month=1, day=1)
        else:
            next_month_boundary = end_date.replace(month=end_date.month + 1, day=1)
        month_boundaries.append(next_month_boundary)

        month_boundary_nums = mdates.date2num([d for d in month_boundaries
                                               if d not in year_change_boundaries])
        year_change_nums = mdates.date2num(year_change_boundaries)

        x_min, x_max = ax.get_xlim()

        for num in month_boundary_nums:
            if x_min <= num <= x_max:
                ax.axvline(x=num, color='gray', linestyle=':', linewidth=0.8)

        for num in year_change_nums:
            if x_min <= num <= x_max:
                ax.axvline(x=num, color='black', linestyle='-', linewidth=1.5)

        for i in range(len(month_boundaries) - 1):
            current_month_date = month_boundaries[i]
            next_month_boundary_date = month_boundaries[i + 1]
            center_mpl = (mdates.date2num(current_month_date) +
                          mdates.date2num(next_month_boundary_date)) / 2

            month_name = month_names.get(current_month_date.month, str(current_month_date.month))
            if x_min <= center_mpl <= x_max:
                ax.text(center_mpl, y_pos_months, month_name,
                        ha='center', va='top', fontsize=6,
                        weight='bold', color='black')

        for year_change_date in year_change_boundaries:
            mpl_year_date = mdates.date2num(year_change_date)
            if x_min <= mpl_year_date <= x_max:
                ax.text(mpl_year_date, y_pos_years, str(year_change_date.year),
                        ha='center', va='top', fontsize=10,
                        weight='bold', color='black')

    def _show_error(self, message: str):
        """Показывает сообщение об ошибке вместо графика."""
        layout = self.layout()
        if self.placeholder_label:
            layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
        error_label = QLabel(message)
        error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(error_label)