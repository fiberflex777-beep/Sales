# base_monthly_analysis_dialog.py
import numpy as np
from matplotlib.cm import Blues
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QGroupBox

from plot_utils import create_empty_graph_message  # публичная функция из общего модуля


class BaseMonthlyAnalysisDialog(QDialog):
    """Базовый класс для диалогов помесячного анализа"""

    def __init__(self, parent=None, movement_data_by_code=None, filtered_codes=None):
        super().__init__(parent)
        self.movement_data_by_code = movement_data_by_code or {}
        self.filtered_codes_set = set(filtered_codes) if filtered_codes else None

        self.setWindowTitle(self.get_window_title())
        self.resize(1400, 800)

        self.figure = None
        self.canvas = None
        self._matplotlib_initialized = False
        self._monthly_data = None
        self._available_years = []

        layout = QVBoxLayout()
        self.setLayout(layout)

        control_group = QGroupBox("")
        control_layout = QHBoxLayout()
        control_group.setLayout(control_layout)
        control_layout.addWidget(QLabel("Год:"))
        self.year_combo = QComboBox()
        control_layout.addWidget(self.year_combo)

        # ----- НАЧАЛО ИЗМЕНЕНИЙ: layout для меток с годовыми итогами -----
        self._yearly_labels_layout = QHBoxLayout()
        control_layout.addLayout(self._yearly_labels_layout)
        # ----- КОНЕЦ ИЗМЕНЕНИЙ -----

        control_layout.addStretch()
        layout.addWidget(control_group)

        self.placeholder_label = QLabel("Загрузка графика...")
        layout.addWidget(self.placeholder_label)

        self._prepare_data()
        self._populate_years_combo()

        # ----- НАЧАЛО ИЗМЕНЕНИЙ: создаём и обновляем метки с итогами -----
        self._create_yearly_totals_labels()
        self._update_yearly_totals()
        # ----- КОНЕЦ ИЗМЕНЕНИЙ -----

        self.year_combo.currentIndexChanged.connect(self.plot)
        self.plot()

    # ----- НАЧАЛО ИЗМЕНЕНИЙ: новые методы для отображения итогов по годам -----
    def _create_yearly_totals_labels(self):
        """Создаёт три метки для отображения итогов за последние 3 года."""
        self._yearly_labels = []
        for i in range(3):  # максимум 3 года
            label = QLabel()
            label.setStyleSheet("font-weight: normal; margin-left: 10px;")  # обычный шрифт для года
            self._yearly_labels_layout.addWidget(label)
            self._yearly_labels.append(label)

    def _update_yearly_totals(self):
        """Обновляет метки с итогами по последним трём годам, используя HTML."""
        if not self._available_years:
            for label in self._yearly_labels:
                label.hide()
            return

        # Показываем до трёх последних лет
        years_to_show = self._available_years[:3]

        for i, label in enumerate(self._yearly_labels):
            if i < len(years_to_show):
                year = years_to_show[i]
                total, prev, growth = self._compute_yearly_totals_and_growth(year)

                # Формируем HTML‑строку
                year_part = str(year)
                total_part = f"<b>{self._format_total(total)}</b>"

                if growth is not None:
                    # Цвет: зелёный для положительного роста, красный для отрицательного
                    color = "green" if growth >= 0 else "red"
                    percent_part = self._format_percent(growth)
                    growth_html = f"<span style='color: {color};'>{percent_part}</span>"
                    text = f"{year_part}: {total_part} ({growth_html})"
                else:
                    text = f"{year_part}: {total_part}"

                label.setText(text)
                label.show()
            else:
                label.hide()
    # ----- КОНЕЦ ИЗМЕНЕНИЙ -----

    # ===== Методы, которые должны быть переопределены в наследниках =====
    def get_window_title(self) -> str:
        return "Анализ"

    def get_ylabel(self) -> str:
        return "Значение"

    def get_title_all_years(self) -> str:
        return "Усреднённые данные по месяцам"

    def get_title_single_year(self, year: int) -> str:
        return f"Данные за {year} год"

    def prepare_data(self):
        """Переопределяется в наследниках: заполняет self._monthly_data"""
        self._monthly_data = {}

    # ===== Внутренние методы =====
    def _prepare_data(self):
        self.prepare_data()
        years = set()
        for (year, month) in self._monthly_data.keys():
            years.add(year)
        self._available_years = sorted(years, reverse=True)

    def _populate_years_combo(self):
        self.year_combo.clear()
        self.year_combo.addItem("Все года", "all")
        for year in self._available_years:
            self.year_combo.addItem(str(year), year)

    def _ensure_matplotlib_loaded(self):
        if self._matplotlib_initialized:
            return
        import matplotlib
        matplotlib.use('QtAgg')
        self.figure = Figure(figsize=(12, 8), facecolor='white')
        self.canvas = FigureCanvas(self.figure)
        layout = self.layout()
        layout.removeWidget(self.placeholder_label)
        self.placeholder_label.hide()
        layout.addWidget(self.canvas)
        self._matplotlib_initialized = True

    def plot(self):
        if not self._monthly_data:
            self._show_no_data_message()
            return
        self._ensure_matplotlib_loaded()
        self.figure.clear()
        selected_year = self.year_combo.currentData()
        try:
            if selected_year == "all":
                self._plot_all_years()
            else:
                year_has_data = any((year == selected_year) for (year, _) in self._monthly_data.keys())
                if not year_has_data:
                    self._show_no_data_message(f"Нет данных за {selected_year} год")
                    return
                self._plot_single_year(selected_year)
        except Exception as e:
            self._show_no_data_message(f"Ошибка построения графика: {str(e)}")
            return
        self.canvas.draw()

    def _plot_all_years(self):
        month_values = {m: [] for m in range(1, 13)}
        for (year, month), value in self._monthly_data.items():
            month_values[month].append(value)
        monthly_averages = []
        for month in range(1, 13):
            values = month_values[month]
            avg = sum(values) / len(values) if values else 0
            monthly_averages.append(avg)
        self._plot_monthly_bars(
            monthly_averages,
            title=self.get_title_all_years(),
            ylabel=self.get_ylabel(),
            fmt='{:.1f}' if 'сумме' in self.get_ylabel() else '{:.0f}'
        )

    # ===== Методы для расчёта динамики =====
    def _get_prev_year_data(self, year):
        """Возвращает словарь {месяц: значение} для предыдущего года"""
        prev_year = year - 1
        return {month: self._monthly_data.get((prev_year, month), 0) for month in range(1, 13)}

    def _compute_yearly_totals_and_growth(self, year):
        """Вычисляет сумму за текущий год, за предыдущий и процент роста"""
        total_current = sum(self._monthly_data.get((year, m), 0) for m in range(1, 13))
        total_prev = sum(self._monthly_data.get((year - 1, m), 0) for m in range(1, 13))
        growth = ((total_current - total_prev) / total_prev * 100) if total_prev != 0 else None
        return total_current, total_prev, growth

    def _compute_monthly_growth(self, year):
        """Возвращает список из 12 элементов – процент роста для каждого месяца (или None)"""
        growth = []
        prev_data = self._get_prev_year_data(year)
        for month in range(1, 13):
            current = self._monthly_data.get((year, month), 0)
            prev = prev_data[month]
            growth.append(((current - prev) / prev * 100) if prev != 0 else None)
        return growth

    def _format_total(self, value):
        """Форматирование итоговой суммы/количества"""
        if 'сумме' in self.get_ylabel():
            return f"{value:,.2f}".replace(',', ' ').replace('.', ',')
        else:
            return f"{int(value):,}".replace(',', ' ')

    def _format_percent(self, value):
        """Форматирование процента (с одним знаком после запятой)"""
        return f"{value:+.1f}%"

    # ===== Построение графика для одного года =====
    def _plot_single_year(self, year):
        monthly_totals = [0] * 12
        for (data_year, month), value in self._monthly_data.items():
            if data_year == year:
                monthly_totals[month - 1] += value

        monthly_growth = self._compute_monthly_growth(year)
        total_current, total_prev, yearly_growth = self._compute_yearly_totals_and_growth(year)

        ax = self.figure.add_subplot(111)
        months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        x_pos = np.arange(len(months))
        colors = Blues(np.linspace(0.4, 0.9, len(monthly_totals)))
        bars = ax.bar(x_pos, monthly_totals, color=colors, alpha=0.8,
                      edgecolor='white', linewidth=2)

        self._style_axes(ax, title=self.get_title_single_year(year), x_label='Месяц', y_label=self.get_ylabel())
        ax.set_xticks(x_pos)
        ax.set_xticklabels(months)

        # Определяем формат для значений
        fmt = '{:.0f}' if 'сумме' not in self.get_ylabel() else '{:.2f}'
        max_val = max(monthly_totals) if monthly_totals else 1
        percent_offset = max_val * 0.005   # небольшой отступ для процентов
        value_offset = max_val * 0.03     # больший отступ для значений

        # Сначала рисуем проценты (ниже)
        for i, (bar, growth) in enumerate(zip(bars, monthly_growth)):
            if growth is not None and monthly_totals[i] > 0:
                height = bar.get_height()
                color = 'green' if growth >= 0 else 'red'
                ax.text(bar.get_x() + bar.get_width()/2., height + percent_offset,
                        self._format_percent(growth), ha='center', va='bottom',
                        fontsize=8, color=color, weight='bold')

        # Затем рисуем значения (выше процентов)
        for bar, val in zip(bars, monthly_totals):
            if val > 0:
                label = fmt.format(val)
                if fmt == '{:.0f}':
                    label = f'{int(val):,}'.replace(',', ' ')
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height() + value_offset,
                        label, ha='center', va='bottom', fontsize=8, color='#333333')

    # ===== Вспомогательные методы для графиков =====
    def _plot_monthly_bars(self, values, title, ylabel, fmt='{:.0f}'):
        ax = self.figure.add_subplot(111)
        months = ['Янв', 'Фев', 'Мар', 'Апр', 'Май', 'Июн',
                  'Июл', 'Авг', 'Сен', 'Окт', 'Ноя', 'Дек']
        x_pos = np.arange(len(months))
        colors = Blues(np.linspace(0.4, 0.9, len(values)))
        bars = ax.bar(x_pos, values, color=colors, alpha=0.8,
                      edgecolor='white', linewidth=2)
        self._style_axes(ax, title=title, x_label='Месяц', y_label=ylabel)
        ax.set_xticks(x_pos)
        ax.set_xticklabels(months)
        self._add_value_labels(bars, values, fmt)

    @staticmethod
    def _style_axes(ax, title, x_label, y_label):
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#dddddd')
        ax.spines['left'].set_color('#dddddd')
        ax.tick_params(colors='#666666', labelsize=9)
        ax.grid(True, linestyle='--', alpha=0.3, linewidth=0.5, axis='y')
        ax.set_axisbelow(True)
        ax.set_xlabel(x_label, fontsize=10)
        ax.set_ylabel(y_label, fontsize=10)
        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_ylim(bottom=0)

    @staticmethod
    def _add_value_labels(bars, values, fmt='{:.1f}'):
        for bar, val in zip(bars, values):
            if val > 0:
                label = fmt.format(val)
                if fmt == '{:.0f}':
                    label = f'{int(val):,}'.replace(',', ' ')
                ax = bar.axes
                ax.text(bar.get_x() + bar.get_width() / 2., bar.get_height(),
                        label, ha='center', va='bottom', fontsize=8, color='#333333')

    def _show_no_data_message(self, message="Нет данных для отображения"):
        self._ensure_matplotlib_loaded()
        self.figure.clear()
        fig = create_empty_graph_message(message)
        self.figure = fig
        self.canvas = FigureCanvas(self.figure)
        layout = self.layout()
        # Очищаем layout и добавляем новый canvas
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget is not None and widget != self.placeholder_label:
                widget.setParent(None)
        layout.addWidget(self.canvas)
        self.canvas.draw()

    def closeEvent(self, event):
        try:
            self.year_combo.currentIndexChanged.disconnect(self.plot)
        except TypeError:
            pass
        super().closeEvent(event)