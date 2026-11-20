# main.py
import sys
import os
import logging
sys.path.insert(0, os.path.dirname(__file__))
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QPixmap, QFont, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")

def create_splash_screen():
    """Создаёт заставку с текстом (можно заменить на загрузку изображения)"""
    pixmap = QPixmap(600, 300)
    pixmap.fill(Qt.GlobalColor.white)
    painter = QPainter(pixmap)
    painter.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
    painter.setPen(QColor(30, 30, 30))
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Загрузка приложения...")
    painter.end()
    return QSplashScreen(pixmap)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Создаём и показываем заставку
    splash = create_splash_screen()
    splash.show()
    app.processEvents()  # гарантируем немедленное отображение

    # Можно обновлять текст на заставке (опционально)
    splash.showMessage("Настройка шрифтов...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.blue)
    app.processEvents()

    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Упрощённая палитра
    from PyQt6.QtGui import QPalette
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(51, 153, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(palette)

    splash.showMessage("Загрузка модулей...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.blue)
    app.processEvents()

    # Отложенный импорт главного окна (тяжёлые модули подгружаются здесь)
    from mainwindow import MainWindow
    window = MainWindow()

    splash.showMessage("Подготовка интерфейса...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, Qt.GlobalColor.blue)
    app.processEvents()

    # Показываем главное окно
    window.showMaximized()

    # Закрываем заставку после полного отображения главного окна
    splash.finish(window)

    # Фоновая предзагрузка модулей (как в исходном коде)
    def preload_critical_modules():
        try:
            import pandas as pd
            _ = pd.DataFrame()
        except ImportError as e:
            logger.warning("Не удалось предзагрузить pandas: %s", e)

    QTimer.singleShot(0, preload_critical_modules)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
