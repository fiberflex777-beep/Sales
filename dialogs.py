# dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QFormLayout, QGroupBox, QProgressBar
)
from PyQt6.QtCore import QSettings

from styles import get_dialog_styles  # импортируем глобально для читаемости


# Настройки по умолчанию и допустимые диапазоны (единственный источник правды)
SETTINGS_DEFAULTS = {
    'log_days': 15,
    'order_days': 30,
    'safety_days': 15,
    'min_total_sales': 5,
    'min_sales_days': 5,
}
SETTINGS_RANGES = {
    'log_days': (1, 365),
    'order_days': (1, 365),
    'safety_days': (0, 365),
    'min_total_sales': (0, 10000),
    'min_sales_days': (0, 365),
}


def _get_qsettings():
    return QSettings("SalesAnalysis", "ReportAnalyzer")


def load_settings():
    """Читает настройки из реестра/ini, подставляя значения по умолчанию."""
    s = _get_qsettings()
    result = {}
    for key, default in SETTINGS_DEFAULTS.items():
        lo, hi = SETTINGS_RANGES[key]
        value = s.value(key, default, type=int)
        result[key] = min(max(value, lo), hi)
    return result


def save_settings(settings):
    """Сохраняет настройки в реестр/ini."""
    s = _get_qsettings()
    for key, value in settings.items():
        s.setValue(key, int(value))
    s.sync()


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

        # Если настройки не переданы, используем сохранённые (или значения по умолчанию)
        if current_settings is None:
            current_settings = load_settings()

        layout = QVBoxLayout()
        self.setLayout(layout)

        settings_group = QGroupBox("Параметры расчета")
        settings_layout = QFormLayout()
        settings_group.setLayout(settings_layout)

        # Спинбоксы создаём из единого описания диапазонов
        self._spinboxes = {}
        labels = {
            'log_days': "Лог. плечо (дни):",
            'order_days': "Кол-во дней заказа:",
            'safety_days': "Страховые дни:",
            'min_total_sales': "Мин. общее кол-во продаж:",
            'min_sales_days': "Мин. дней продаж:",
        }
        for key in SETTINGS_DEFAULTS:
            lo, hi = SETTINGS_RANGES[key]
            spin = QSpinBox()
            spin.setRange(lo, hi)
            spin.setValue(current_settings.get(key, SETTINGS_DEFAULTS[key]))
            settings_layout.addRow(labels[key], spin)
            self._spinboxes[key] = spin

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
        return {key: spin.value() for key, spin in self._spinboxes.items()}