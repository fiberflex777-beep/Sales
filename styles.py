# styles.py
"""Централизованное хранение стилей приложения (современная версия)"""

_COMMON_STYLES = None

def _get_common_styles():
    """Возвращает общие стили для всех компонентов (ленивое кэширование)"""
    global _COMMON_STYLES
    if _COMMON_STYLES is None:
        _COMMON_STYLES = {
            'dialog': """
                QDialog {
                    background-color: #f8fafc;
                    border-radius: 12px;
                }
                QLabel {
                    color: #1e293b;
                    font-size: 12px;
                    font-weight: 400;
                }
                QGroupBox {
                    font-weight: 600;
                    font-size: 13px;
                    color: #0f172a;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    margin-top: 0px;
                    padding-top: 8px;
                    background-color: #ffffff;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    padding: 0 2px 0 2px;
                    color: #334155;
                }
                QSpinBox, QDoubleSpinBox {
                    border: 1px solid #cbd5e1;
                    border-radius: 8px;
                    padding: 6px;
                    background-color: #ffffff;
                    color: #0f172a;
                    selection-background-color: #3b82f6;
                    min-height: 20px;
                }
                QSpinBox:focus, QDoubleSpinBox:focus {
                    border: 2px solid #3b82f6;
                    outline: none;
                }
                QPushButton {
                    background-color: #3b82f6;
                    color: white;
                    border: none;
                    padding: 8px 18px;
                    border-radius: 8px;
                    font-size: 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #2563eb;
                }
                QPushButton:pressed {
                    background-color: #1d4ed8;
                }
                QPushButton#cancel_button {
                    background-color: #ef4444;
                }
                QPushButton#cancel_button:hover {
                    background-color: #dc2626;
                }
                QPushButton#cancel_button:pressed {
                    background-color: #b91c1c;
                }
                QProgressBar {
                    border: 1px solid #e2e8f0;
                    border-radius: 8px;
                    text-align: center;
                    color: #0f172a;
                    font-weight: 600;
                    background-color: #f1f5f9;
                }
                QProgressBar::chunk {
                    background-color: #3b82f6;
                    border-radius: 7px;
                }
                /* Стили для таблиц внутри диалогов (единообразие с главной таблицей) */
                QTableWidget {
                    background-color: #ffffff;
                    alternate-background-color: #f8fafc;
                    selection-background-color: #dbeafe;
                    selection-color: #0f172a;
                    gridline-color: #e2e8f0;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                }
                QTableWidget::item {
                    padding: 2px;
                }
                QHeaderView::section {
                    background-color: #f8fafc;
                    border: none;
                    border-bottom: 2px solid #e2e8f0;
                    font-weight: 600;
                    font-size: 11px;
                    color: #475569;
                }
            """,
            'main_window': """
                QMainWindow {
                    background-color: #f1f5f9;
                }
                QMenuBar {
                    background-color: #ffffff;
                    border-bottom: 1px solid #e2e8f0;
                    padding: 4px;
                }
                QMenuBar::item {
                    padding: 6px 12px;
                    background: transparent;
                    border-radius: 6px;
                    color: #334155;
                }
                QMenuBar::item:selected {
                    background-color: #e2e8f0;
                }
                QMenuBar::item:pressed {
                    background-color: #cbd5e1;
                }
                QMenu {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                    padding: 6px;
                }
                QMenu::item {
                    padding: 8px 24px 8px 24px;
                    border-radius: 6px;
                    color: #334155;
                }
                QMenu::item:selected {
                    background-color: #e2e8f0;
                }
                QToolBar {
                    background-color: #ffffff;
                    border: none;
                    border-bottom: 1px solid #e2e8f0;
                    padding: 4px;
                    spacing: 4px;
                }
                QLineEdit {
                    border: 1px solid #cbd5e1;
                    border-radius: 4px;
                    padding: 1px 1px;
                    background-color: #ffffff;
                    color: #0f172a;
                    selection-background-color: #3b82f6;
                }
                QLineEdit:focus {
                    border: 2px solid #3b82f6;
                }
                QGroupBox {
                    background-color: #ffffff;
                    border: 1px solid #e2e8f0;
                    border-radius: 12px;
                    margin-top: 12px;
                    font-weight: 600;
                    font-size: 13px;
                    color: #0f172a;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 12px;
                    color: #334155;
                }
                QTableView {
                    background-color: #ffffff;
                    alternate-background-color: #f8fafc;
                    selection-background-color: #dbeafe;
                    selection-color: #0f172a;
                    gridline-color: #e2e8f0;
                    border: 1px solid #e2e8f0;
                    border-radius: 10px;
                }
                QHeaderView::section {
                    background-color: #f8fafc;
                    border: none;
                    border-bottom: 2px solid #e2e8f0;
                    font-weight: 600;
                    font-size: 11px;
                    color: #475569;
                }
                QSplitter::handle {
                    background-color: #cbd5e1;
                    height: 2px;
                }
                QStatusBar {
                    background-color: #ffffff;
                    border-top: 1px solid #e2e8f0;
                    color: #475569;
                }
            """
        }
    return _COMMON_STYLES


def get_dialog_styles():
    """Возвращает стили для диалоговых окон"""
    common = _get_common_styles()
    return common['dialog']


def get_main_window_styles():
    """Возвращает стили для главного окна"""
    common = _get_common_styles()
    return common['main_window']