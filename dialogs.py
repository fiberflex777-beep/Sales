# dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QFormLayout, QGroupBox, QProgressBar
)

from styles import get_dialog_styles  # импортируем глобально для читаемости


def apply_dialog_styles(dialog):
    """Применяет стили к диалоговому окну"""
    dialog.setStyleSheet(get_dialog_styles())


class ProgressDialog(QDialog):
    """Диалог отображения прогресса расчёта"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Прогресс")
        self.setModal(True)
        self.resize(300, 100)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.label = QLabel("Выполняется расчет...")
        layout.addWidget(self.label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setObjectName("cancel_button")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        apply_dialog_styles(self)


class SettingsDialog(QDialog):
    """Диалог настроек параметров расчёта"""

    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.resize(400, 250)

        # Если настройки не переданы, используем значения по умолчанию
        if current_settings is None:
            current_settings = {}

        layout = QVBoxLayout()
        self.setLayout(layout)

        settings_group = QGroupBox("Параметры расчета")
        settings_layout = QFormLayout()
        settings_group.setLayout(settings_layout)

        # Лог. плечо
        self.log_days_spinbox = QSpinBox()
        self.log_days_spinbox.setRange(1, 365)
        self.log_days_spinbox.setValue(current_settings.get('log_days', 15))
        settings_layout.addRow("Лог. плечо (дни):", self.log_days_spinbox)

        # Кол-во дней заказа
        self.order_days_spinbox = QSpinBox()
        self.order_days_spinbox.setRange(1, 365)
        self.order_days_spinbox.setValue(current_settings.get('order_days', 30))
        settings_layout.addRow("Кол-во дней заказа:", self.order_days_spinbox)

        # Страховые дни
        self.safety_days_spinbox = QSpinBox()
        self.safety_days_spinbox.setRange(0, 365)
        self.safety_days_spinbox.setValue(current_settings.get('safety_days', 15))
        settings_layout.addRow("Страховые дни:", self.safety_days_spinbox)

        # Минимальное общее количество продаж
        self.min_total_sales_spinbox = QSpinBox()
        self.min_total_sales_spinbox.setRange(0, 10000)
        self.min_total_sales_spinbox.setValue(current_settings.get('min_total_sales', 5))
        settings_layout.addRow("Мин. общее кол-во продаж:", self.min_total_sales_spinbox)

        # Минимальное количество дней продаж
        self.min_sales_days_spinbox = QSpinBox()
        self.min_sales_days_spinbox.setRange(0, 365)
        self.min_sales_days_spinbox.setValue(current_settings.get('min_sales_days', 5))
        settings_layout.addRow("Мин. дней продаж:", self.min_sales_days_spinbox)

        layout.addWidget(settings_group)

        # Кнопки OK/Отмена
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.cancel_button = QPushButton("Отмена")
        self.cancel_button.setObjectName("cancel_button")

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        apply_dialog_styles(self)

    def get_settings(self):
        """Возвращает словарь с настройками из полей ввода"""
        return {
            'log_days': self.log_days_spinbox.value(),
            'order_days': self.order_days_spinbox.value(),
            'safety_days': self.safety_days_spinbox.value(),
            'min_total_sales': self.min_total_sales_spinbox.value(),
            'min_sales_days': self.min_sales_days_spinbox.value()
        }