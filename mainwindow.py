import re
from datetime import datetime
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QLabel, QGroupBox, QSplitter, QFrame, QPushButton
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QTimer

from table_manager import TableManager
from plot_manager import PlotManager
from models import PandasTableModel

# Миксины с вынесенными методами
from mainwindow_data import DataMixin
from mainwindow_dialogs import DialogsMixin

if TYPE_CHECKING:
    import pandas as pd


class MainWindow(QMainWindow, DataMixin, DialogsMixin):
    def __init__(self):
        super().__init__()

        # Данные
        self.original_data = None          # полный DataFrame после расчёта
        self.raw_df = None                 # сырой DataFrame из Excel
        self.headers_row_index = -1        # индекс строки с заголовками
        self.movement_data_by_code = {}    # данные движений по кодам (для графиков/анализов)
        self.movement_details_by_code = {} # детальные данные движений (для диалога)
        self.worker_thread = None

        # Компоненты UI (будут инициализированы в setup_*)
        self.search_line = None
        self.clear_filter_button = None
        self.period_label = None
        self.total_stock_sum_label = None
        self.clear_order_button = None
        self.optimal_order_button = None
        self.settings_button = None
        self.total_sum_label = None
        self.splitter = None
        self.model = None
        self.table_manager = None
        self.plot_manager = None

        # Ленивый импорт pandas
        self._pd = None

        # Таймер для дебаунса поиска
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._apply_filter_debounced)

        # Таймер для дебаунса графика
        self.graph_timer = QTimer()
        self.graph_timer.setSingleShot(True)
        self.graph_timer.timeout.connect(self._update_graph_debounced)
        self._last_selected_code = None   # для предотвращения лишних обновлений

        # Настройки по умолчанию
        self.settings = {
            'log_days': 15,
            'order_days': 30,
            'safety_days': 15,
            'min_total_sales': 5,
            'min_sales_days': 5
        }

        # Сохранённый текст фильтра для восстановления после перерасчёта
        self._saved_filter_text = None

        self.setWindowTitle("Анализ отчета по продажам")
        self.apply_styles()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)   # убираем все отступы
        central_widget.setLayout(layout)

        self.setup_search_panel(layout)
        self.setup_main_area(layout)
        self.setup_status_bar()
        self.setup_menu()

    # ------------------------------------------------------------------
    # Ленивая загрузка pandas
    # ------------------------------------------------------------------
    def _get_pd(self):
        """Ленивый импорт pandas"""
        if self._pd is None:
            import pandas
            self._pd = pandas
        return self._pd

    # ------------------------------------------------------------------
    # Инициализация компонентов (ленивая загрузка)
    # ------------------------------------------------------------------
    def _ensure_managers_loaded(self):
        """Ленивая инициализация менеджеров таблицы и графиков"""
        if self.table_manager is None:
            self.table_manager = TableManager(self)
            if self.splitter is not None:
                self.splitter.replaceWidget(0, self.table_manager.table_frame)

        if self.plot_manager is None:
            self.plot_manager = PlotManager(self)
            if self.splitter is not None:
                self.splitter.replaceWidget(1, self.plot_manager.graph_frame)

    def _ensure_model_loaded(self):
        """Ленивая инициализация модели таблицы"""
        if self.model is None:
            self.model = PandasTableModel()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def apply_styles(self):
        from styles import get_main_window_styles
        self.setStyleSheet(get_main_window_styles())

    def _apply_compact_menu_style(self, menubar):
        """Уменьшает высоту строки меню и отступы пунктов."""
        menubar.setContentsMargins(0, 0, 0, 0)
        menubar.setFixedHeight(24)          # обычная строка меню ~30 px
        menubar.setStyleSheet("""
            QMenuBar {
                background: transparent;
                border: none;
                border-bottom: 1px solid palette(mid);
                padding: 0px;
                margin: 0px;
                spacing: 0px;
                font-size: 12px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 2px 8px;
                margin: 1px 0px;
                border-radius: 3px;
            }
            QMenuBar::item:selected,
            QMenuBar::item:pressed {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QMenu {
                font-size: 12px;
                padding: 2px 0px;
            }
            QMenu::item {
                padding: 3px 22px 3px 10px;
            }
            QMenu::separator {
                height: 1px;
                margin: 3px 6px;
                background: palette(mid);
            }
        """)

    def setup_search_panel(self, layout):
        """Компактная верхняя панель: всё в одну строку, без рамок QGroupBox."""
        panel = QFrame()
        panel.setObjectName("topPanel")
        panel.setStyleSheet(
            "QFrame#topPanel { border: none; border-bottom: 1px solid palette(mid); }"
        )

        row = QHBoxLayout(panel)
        row.setContentsMargins(8, 4, 8, 4)   # минимальные отступы вместо полей QGroupBox
        row.setSpacing(8)

        def add_separator():
            line = QFrame()
            line.setFrameShape(QFrame.Shape.VLine)
            line.setFrameShadow(QFrame.Shadow.Plain)
            line.setFixedHeight(18)
            row.addWidget(line)

        # --- Поиск + сброс фильтра (визуально одна группа) ---
        self.search_line = QLineEdit()
        self.search_line.setPlaceholderText("Поиск: код или наименование…")
        self.search_line.setFixedWidth(260)
        self.search_line.setFixedHeight(26)
        self.search_line.textChanged.connect(self.on_search_changed)

        self.clear_filter_button = QPushButton("✕")
        self.clear_filter_button.setFixedSize(22, 22)
        self.clear_filter_button.setToolTip("Сбросить фильтр")
        self.clear_filter_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_filter_button.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; color: #888; }"
            "QPushButton:hover { color: #c62828; }"
        )
        self.clear_filter_button.clicked.connect(self.clear_filter)

        search_box = QHBoxLayout()
        search_box.setSpacing(2)
        search_box.addWidget(self.search_line)
        search_box.addWidget(self.clear_filter_button)
        row.addLayout(search_box)

        # --- Период анализа ---
        self.period_label = QLabel("Период анализа: ")
        self.period_label.setStyleSheet("font-weight: bold;")
        row.addWidget(self.period_label)

        row.addStretch(1)

        # --- Кнопки заказа: короткие подписи, полные названия в подсказках ---
        self.clear_order_button = QPushButton("Очистить")
        self.clear_order_button.setToolTip("Очистить заказ")
        self.clear_order_button.clicked.connect(self.clear_order)

        self.optimal_order_button = QPushButton("Автозаказ")
        self.optimal_order_button.setToolTip("Рассчитать оптимальный заказ")
        self.optimal_order_button.clicked.connect(self.set_optimal_order)

        self.settings_button = QPushButton("⚙")
        self.settings_button.setToolTip("Настройка автозаказа")
        self.settings_button.setFixedWidth(28)
        self.settings_button.clicked.connect(self.open_settings)

        for btn in (self.clear_order_button, self.optimal_order_button, self.settings_button):
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(btn)

        add_separator()

        # --- Суммы: в одну строку вместо двух этажей ---
        self.total_stock_sum_label = QLabel("Сумма остатков: 0,00")
        self.total_stock_sum_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.total_stock_sum_label.setToolTip("Стоимость остатков по видимым строкам")

        self.total_sum_label = QLabel("Сумма заказа: 0,00")
        self.total_sum_label.setStyleSheet(
            "font-weight: bold; font-size: 12px; color: green;"
        )
        self.total_sum_label.setToolTip("Сумма заказа по видимым строкам")

        row.addWidget(self.total_stock_sum_label)
        row.addWidget(self.total_sum_label)

        layout.addWidget(panel)

    def setup_main_area(self, layout):
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter)

        table_placeholder = QFrame()
        table_placeholder.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        table_placeholder.setMinimumHeight(200)
        self.splitter.addWidget(table_placeholder)

        graph_placeholder = QFrame()
        graph_placeholder.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        graph_placeholder.setMinimumHeight(150)
        self.splitter.addWidget(graph_placeholder)

    def setup_status_bar(self):
        self.statusBar().showMessage("Файл не загружен")

    def setup_menu(self):
        menubar = self.menuBar()
        self._apply_compact_menu_style(menubar)   # компактный вид строки меню

        file_menu = menubar.addMenu("Файл")

        open_action = QAction("Открыть файл", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        save_order_action = QAction("Сохранить заказ", self)
        save_order_action.setShortcut("Ctrl+S")
        save_order_action.triggered.connect(self.save_order_to_excel)
        file_menu.addAction(save_order_action)

        # Пункт меню: Импортировать заказ
        import_order_action = QAction("Импортировать заказ", self)
        import_order_action.triggered.connect(self.import_order_from_file)
        file_menu.addAction(import_order_action)

        analysis_menu = menubar.addMenu("Анализ")

        # Помесячный анализ в штуках (бывший анализ сезонности)
        quantity_action = QAction("Помесячный анализ в штуках", self)
        quantity_action.triggered.connect(self.open_monthly_quantity_analysis)
        analysis_menu.addAction(quantity_action)

        # Помесячный анализ в сумме
        sum_action = QAction("Помесячный анализ в сумме", self)
        sum_action.triggered.connect(self.open_monthly_sum_analysis)
        analysis_menu.addAction(sum_action)

        # Распределение остатков по категориям
        distribution_action = QAction("Распределение остатков по категориям", self)
        distribution_action.triggered.connect(self.open_stock_distribution_dialog)
        analysis_menu.addAction(distribution_action)

        # Анализ покупателей
        customer_action = QAction("Анализ покупателей", self)
        customer_action.triggered.connect(self.open_customer_analysis_dialog)
        analysis_menu.addAction(customer_action)

        # Анализ остатков в деньгах
        stock_value_action = QAction("Анализ остатков в деньгах", self)
        stock_value_action.triggered.connect(self.open_stock_value_analysis)
        analysis_menu.addAction(stock_value_action)

    # ------------------------------------------------------------------
    # Обработчики событий
    # ------------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        if self.splitter is not None:
            self.splitter.setSizes([self.height() * 2 // 3, self.height() // 3])

    def on_search_changed(self, _text):
        """Обработчик изменения текста поиска с дебаунсом"""
        self.search_timer.start(300)  # задержка 300 мс

    def _apply_filter_debounced(self):
        """Применяет фильтр после пауды в вводе"""
        if self.model:
            self.model.filter_data(self.search_line.text())
            self.update_total_sum()
            self.update_total_stock_sum()

    def clear_filter(self):
        """Очищает поле поиска и сбрасывает фильтр"""
        self.search_line.clear()  # очистит текст и вызовет textChanged

    def on_table_selection_changed(self, _current, _previous):
        """Запускает таймер для отложенного обновления графика"""
        self.graph_timer.start(250)

    def _update_graph_debounced(self):
        """Обновляет график для текущей выделенной строки"""
        if not self.table_manager or not self.table_manager.table.selectionModel().hasSelection():
            return

        current_index = self.table_manager.table.currentIndex()
        if not current_index.isValid():
            return

        model = current_index.model()
        if model is None:
            return

        code_index = model.index(current_index.row(), 0)
        code = code_index.data(Qt.ItemDataRole.DisplayRole)
        if not code:
            return

        if code == self._last_selected_code:
            return
        self._last_selected_code = code

        if self.plot_manager:
            self.plot_manager.show_stock_graph(current_index)

    # ------------------------------------------------------------------
    # Обновление сумм
    # ------------------------------------------------------------------
    def update_total_sum(self):
        """Обновляет отображение общей суммы заказа, используя кэшированное значение из модели"""
        if self.model:
            total_sum = self.model.get_total_sum()
            formatted_total = f"{total_sum:,.2f}".replace(',', ' ').replace('.', ',')
            self.total_sum_label.setText(f"Сумма заказа: {formatted_total}")
        else:
            self.total_sum_label.setText("Сумма заказа: 0,00")

    def update_total_stock_sum(self):
        """Обновляет отображение общей стоимости остатков с учётом фильтра."""
        if self.model:
            total_stock = self.model.get_total_stock_value()
            formatted = f"{total_stock:,.2f}".replace(',', ' ').replace('.', ',')
            self.total_stock_sum_label.setText(f"Сумма остатков: {formatted}")
        else:
            self.total_stock_sum_label.setText("Сумма остатков: 0,00")

    # ------------------------------------------------------------------
    # Корректное завершение программы
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        """Обработка закрытия главного окна: завершаем фоновый поток, если он ещё работает."""
        if self.worker_thread and self.worker_thread.isRunning():
            # Запрашиваем отмену вычислений
            self.worker_thread.cancel()
            # Ждём завершения потока не более 3 секунд
            if not self.worker_thread.wait(3000):
                # Если поток не завершился, принудительно завершаем (допустимо при выходе)
                self.worker_thread.terminate()
                self.worker_thread.wait()
        event.accept()   # разрешаем закрытие