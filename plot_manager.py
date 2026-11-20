# plot_manager.py
from datetime import datetime
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QMessageBox, QLabel
from PyQt6.QtCore import Qt, QModelIndex

import matplotlib.dates as mdates
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from plot_utils import create_empty_graph_message  # импортируем общую функцию


class PlotManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.figure = None
        self.ax = None
        self.canvas = None
        self._pd = None

        self.graph_frame = QFrame()
        self.graph_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        graph_layout = QVBoxLayout()
        self.graph_frame.setLayout(graph_layout)

        self.placeholder_label = QLabel("График будет отображен после выбора товара")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graph_layout.addWidget(self.placeholder_label)

    @property
    def pd(self):
        if self._pd is None:
            import pandas as pd
            self._pd = pd
        return self._pd

    def _ensure_matplotlib_loaded(self):
        """Ленивая инициализация matplotlib."""
        if self.canvas is not None:
            self.canvas.deleteLater()
            self.canvas = None
            self.figure = None
            self.ax = None

        self.figure, self.ax = self._create_figure_and_axes()
        self.canvas = FigureCanvas(self.figure)
        self._set_canvas(self.canvas)

    @staticmethod
    def _create_figure_and_axes(figsize=(16, 4), facecolor='white'):
        """Создаёт фигуру и оси с базовым оформлением."""
        import matplotlib
        matplotlib.use('QtAgg')
        fig = Figure(figsize=figsize, facecolor=facecolor)
        ax = fig.add_subplot(111, facecolor=facecolor)
        ax.tick_params(axis='x', colors='black')
        ax.tick_params(axis='y', colors='black')
        ax.spines['top'].set_color('0.5')
        ax.spines['bottom'].set_color('0.5')
        ax.spines['left'].set_color('0.5')
        ax.spines['right'].set_color('0.5')
        return fig, ax

    def _set_canvas(self, new_canvas):
        """Заменяет текущий canvas на новый в layout графика."""
        layout = self.graph_frame.layout()
        if self.canvas is not None:
            layout.removeWidget(self.canvas)
            self.canvas.deleteLater()
            self.canvas = None
        if self.placeholder_label.isVisible():
            layout.removeWidget(self.placeholder_label)
            self.placeholder_label.hide()
        layout.addWidget(new_canvas)
        self.canvas = new_canvas

    def _show_no_data_message(self):
        """Отображает сообщение об отсутствии данных."""
        if not self.canvas:
            self._ensure_matplotlib_loaded()
        # Используем общую функцию для создания пустого графика
        fig = create_empty_graph_message('Нет данных для отображения графика')
        self.figure = fig
        self.ax = fig.axes[0]
        self.canvas = FigureCanvas(fig)
        self._set_canvas(self.canvas)
        self.canvas.draw()

    def show_stock_graph(self, current_index: QModelIndex, _previous_index: QModelIndex = None):
        """
        Отображает график остатков для товара, выбранного в таблице.
        Параметр _previous_index не используется, но сохранён для совместимости с сигналом.
        """
        if (self.main_window.original_data is None or
            self.main_window.original_data.empty or
            not self.main_window.movement_data_by_code):
            self._show_no_data_message()
            return

        if not current_index.isValid():
            self._show_no_data_message()
            return

        model = current_index.model()
        if model is None:
            self._show_no_data_message()
            return

        product_code = model.data(model.index(current_index.row(), 0),
                                  Qt.ItemDataRole.DisplayRole)
        if not product_code:
            self._show_no_data_message()
            return

        product_row = self.main_window.original_data[
            self.main_window.original_data['Код'] == product_code
        ]
        if product_row.empty:
            self._show_no_data_message()
            return

        product_name = product_row['Наименование'].iloc[0]

        if product_code not in self.main_window.movement_data_by_code:
            self._show_no_data_message()
            return

        movement_records = self.main_window.movement_data_by_code[product_code]

        try:
            initial_stock = float(product_row['Начальный остаток'].iloc[0])
        except (ValueError, TypeError):
            initial_stock = 0.0

        stock_changes = {}
        for date, incoming, outgoing in movement_records:
            change = incoming - outgoing
            if date in stock_changes:
                stock_changes[date] += change
            else:
                stock_changes[date] = change

        period_text = self.main_window.period_label.text().replace("Период анализа: ", "")
        import re
        date_pattern = r'(\d{2}\.\d{2}\.\d{2,4})\s*-\s*(\d{2}\.\d{2}\.\d{2,4})'
        match = re.search(date_pattern, period_text)
        if not match:
            self._show_no_data_message()
            return

        start_str, end_str = match.groups()

        def parse_date(date_str):
            for fmt in ('%d.%m.%Y', '%d.%m.%y'):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
            raise ValueError(f"Не удалось распознать дату: {date_str}")

        try:
            start_date = parse_date(start_str)
            end_date = parse_date(end_str)
        except ValueError:
            self._show_no_data_message()
            return

        pd = self.pd
        # Преобразуем DatetimeIndex в Series, чтобы получить доступ к .dt.date (более дружелюбно для линтера)
        date_range_series = pd.Series(pd.date_range(start=start_date, end=end_date, freq='D'))
        date_range = date_range_series.dt.date.tolist()

        daily_stocks = []
        current_stock = initial_stock

        for date in date_range:
            if date in stock_changes:
                current_stock += stock_changes[date]
            daily_stocks.append(current_stock)

        avg_sales = pd.to_numeric(product_row['Средняя продажа'].iloc[0], errors='coerce')
        if pd.isna(avg_sales):
            avg_sales = 0.0

        safety_stock = pd.to_numeric(product_row['Страховой запас'].iloc[0], errors='coerce')
        if pd.isna(safety_stock):
            safety_stock = 0.0

        order_qty = pd.to_numeric(product_row['Оптимальный заказ'].iloc[0], errors='coerce')
        if pd.isna(order_qty):
            order_qty = 0.0

        status = str(product_row['Статус заказа'].iloc[0])

        try:
            canvas = self._build_stock_graph(
                _product_name=product_name, _product_code=product_code,
                dates=date_range, stocks=daily_stocks,
                start_date=start_date, end_date=end_date,
                _avg_sales=avg_sales, safety_stock=safety_stock,
                _order_qty=order_qty, _status=status
            )
            self._set_canvas(canvas)
            self.main_window.statusBar().showMessage(f"График для {product_name} отображен")
        except Exception as e_graph:
            import traceback
            traceback.print_exc()
            self._show_no_data_message()
            QMessageBox.critical(self.main_window, "Ошибка графика",
                                 f"Произошла ошибка при отображении графика:\n{str(e_graph)}")

    def _build_stock_graph(self, _product_name, _product_code, dates, stocks,
                           start_date, end_date, _avg_sales, safety_stock,
                           _order_qty, _status):
        """Строит современный график остатков и возвращает готовый canvas."""
        if len(dates) == 0 or len(stocks) == 0:
            fig = create_empty_graph_message("Нет данных для отображения")
            canvas = FigureCanvas(fig)
            canvas.draw()
            return canvas

        fig, ax = self._create_figure_and_axes()

        # ---- Настройка современного стиля для осей ----
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#dddddd')
        ax.spines['left'].set_color('#dddddd')
        ax.tick_params(colors='#666666', labelsize=9)
        ax.grid(True, linestyle='--', alpha=0.3, linewidth=0.5)
        ax.set_axisbelow(True)

        # ---- Построение данных ----
        mpl_dates = mdates.date2num(self.pd.to_datetime(dates))
        line_color = '#3399ff'

        ax.plot(mpl_dates, stocks, color=line_color, linestyle='-',
                linewidth=1.5, label='Остаток')

        ax.fill_between(mpl_dates, stocks, 0,
                        color=line_color,
                        alpha=0.4,
                        edgecolor=None)

        ax.set_xlim(mpl_dates[0], mpl_dates[-1])
        ax.margins(x=0)
        ax.set_ylim(bottom=0)

        # Страховой запас
        if safety_stock > 0:
            current_xlim = ax.get_xlim()
            ax.hlines(y=safety_stock, xmin=current_xlim[0], xmax=current_xlim[1],
                      color='#e74c3c', linestyle='--', linewidth=1.2, label='Страховой запас')

        if len(ax.lines) > 1:
            ax.legend(loc='upper right', fontsize=9, frameon=False)

        self._add_month_year_markers(ax, start_date, end_date)

        ax.set_ylabel('Остаток', fontsize=10)
        ax.tick_params(axis='x', which='both', bottom=False, top=False,
                       labelbottom=False, labeltop=False)

        fig.tight_layout()
        canvas = FigureCanvas(fig)
        canvas.draw()
        return canvas

    @staticmethod
    def _add_month_year_markers(ax, start_date, end_date):
        """Добавление вертикальных линий и подписей месяцев/годов."""
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