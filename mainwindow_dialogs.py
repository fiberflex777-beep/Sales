# mainwindow_dialogs.py
from PyQt6.QtWidgets import QMessageBox, QDialog
from PyQt6.QtCore import QObject, Qt

from dialogs import SettingsDialog, save_settings
from monthly_quantity_analysis_dialog import MonthlyQuantityAnalysisDialog
from monthly_sum_analysis_dialog import MonthlySumAnalysisDialog
from stock_distribution_dialog import StockDistributionDialog
from customer_analysis_dialog import CustomerAnalysisDialog
from movement_details_dialog import MovementDetailsDialog
from stock_value_analysis_dialog import StockValueAnalysisDialog  # <-- НОВЫЙ ИМПОРТ


class DialogsMixin(QObject):
    """Миксин с методами для открытия диалоговых окон."""

    # ------------------------------------------------------------------
    # Диалоги
    # ------------------------------------------------------------------
    def open_settings(self):
        """Открывает диалог настроек"""
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()
            if new_settings != self.settings:
                self.settings = new_settings
                save_settings(new_settings)   # сохраняем между запусками
                if self.original_data is not None and not self.original_data.empty:
                    self.recalculate_with_new_settings()

    # ------------------------------------------------------------------
    # Помесячный анализ в штуках (бывший анализ сезонности)
    # ------------------------------------------------------------------
    def open_monthly_quantity_analysis(self):
        """Открывает диалог помесячного анализа продаж в штуках"""
        if not self.movement_data_by_code:
            QMessageBox.information(
                self, "Информация",
                "Нет данных для анализа. Сначала загрузите файл."
            )
            return

        filtered_codes = []
        if self.model:
            filtered_codes = self.model.get_filtered_codes()

        dialog = MonthlyQuantityAnalysisDialog(
            self,
            self.movement_data_by_code,
            filtered_codes
        )
        dialog.exec()

    # ------------------------------------------------------------------
    # Помесячный анализ в сумме (новый)
    # ------------------------------------------------------------------
    def open_monthly_sum_analysis(self):
        """Открывает диалог помесячного анализа продаж в денежном выражении"""
        if not self.movement_data_by_code:
            QMessageBox.information(
                self, "Информация",
                "Нет данных для анализа. Сначала загрузите файл."
            )
            return

        filtered_codes = []
        if self.model:
            filtered_codes = self.model.get_filtered_codes()

        # Создаем словарь цен по кодам из исходных данных
        price_by_code = {}
        if self.original_data is not None and 'Код' in self.original_data.columns and 'Цена' in self.original_data.columns:
            for _, row in self.original_data.iterrows():
                code = str(row['Код'])
                try:
                    price = float(row['Цена'])
                except (ValueError, TypeError):
                    price = 0.0
                price_by_code[code] = price

        dialog = MonthlySumAnalysisDialog(
            self,
            self.movement_data_by_code,
            filtered_codes,
            price_by_code
        )
        dialog.exec()

    # ------------------------------------------------------------------
    # НОВЫЙ МЕТОД: Открытие диалога распределения остатков по категориям
    # ------------------------------------------------------------------
    def open_stock_distribution_dialog(self):
        """Открывает диалог распределения остатков по категориям"""
        if self.model is None or self.original_data is None or self.original_data.empty:
            QMessageBox.information(
                self, "Информация",
                "Нет данных для анализа. Сначала загрузите файл."
            )
            return

        dialog = StockDistributionDialog(self, self.model)
        dialog.exec()

    # ------------------------------------------------------------------
    # НОВЫЙ МЕТОД: Открытие диалога анализа покупателей (с учётом фильтра)
    # ------------------------------------------------------------------
    def open_customer_analysis_dialog(self):
        """Открывает диалог анализа покупателей."""
        if not self.movement_details_by_code:
            QMessageBox.information(
                self, "Информация",
                "Нет данных для анализа. Сначала загрузите файл."
            )
            return

        # Получаем отфильтрованные коды из текущей модели
        filtered_codes = []
        if self.model is not None:
            filtered_codes = self.model.get_filtered_codes()

        # Словарь цен по кодам товаров
        price_by_code = {}
        if self.original_data is not None and 'Код' in self.original_data.columns:
            for _, row in self.original_data.iterrows():
                code = str(row['Код'])
                try:
                    price = float(row['Цена'])
                except (ValueError, TypeError):
                    price = 0.0
                price_by_code[code] = price

        dialog = CustomerAnalysisDialog(
            self,
            self.movement_details_by_code,
            price_by_code,
            filtered_codes          # ← передаём список отфильтрованных кодов
        )
        dialog.exec()

    # ------------------------------------------------------------------
    # НОВЫЙ МЕТОД: Показать детали движений товара (вызывается по двойному клику)
    # ------------------------------------------------------------------
    def show_movement_details(self, index):
        """Открывает диалог с детализацией движений для выбранного товара."""
        if not index.isValid():
            return
        model = index.model()
        if model is None:
            return
        code = model.data(model.index(index.row(), 0), Qt.ItemDataRole.DisplayRole)
        if not code:
            return

        # Получить начальный остаток и цену из original_data
        if self.original_data is None or self.original_data.empty:
            QMessageBox.warning(self, "Предупреждение", "Нет данных о товаре.")
            return
        row = self.original_data[self.original_data['Код'] == code]
        if row.empty:
            QMessageBox.warning(self, "Предупреждение", f"Товар с кодом {code} не найден в данных.")
            return
        try:
            initial_stock = float(row['Начальный остаток'].iloc[0])
        except (ValueError, TypeError):
            initial_stock = 0.0
        try:
            price = float(row['Цена'].iloc[0])
        except (ValueError, TypeError):
            price = 0.0

        # Получить детали движений
        details = self.movement_details_by_code.get(code, [])
        if not details:
            QMessageBox.information(self, "Информация", "Нет данных о движениях для этого товара.")
            return

        dialog = MovementDetailsDialog(self, code, initial_stock, price, details)
        dialog.exec()

    # ------------------------------------------------------------------
    # НОВЫЙ МЕТОД: Анализ остатков в деньгах
    # ------------------------------------------------------------------
    def open_stock_value_analysis(self):
        """Открывает диалог анализа суммарных остатков в денежном выражении."""
        if not self.movement_data_by_code:
            QMessageBox.information(
                self, "Информация",
                "Нет данных для анализа. Сначала загрузите файл."
            )
            return

        # Получаем отфильтрованные коды из модели
        filtered_codes = []
        if self.model:
            filtered_codes = self.model.get_filtered_codes()

        # Словарь цен и начальных остатков из original_data
        price_by_code = {}
        initial_stock_by_code = {}
        if self.original_data is not None and not self.original_data.empty:
            for _, row in self.original_data.iterrows():
                code = str(row['Код'])
                try:
                    price = float(row['Цена'])
                except (ValueError, TypeError):
                    price = 0.0
                try:
                    init_stock = float(row['Начальный остаток'])
                except (ValueError, TypeError):
                    init_stock = 0.0
                price_by_code[code] = price
                initial_stock_by_code[code] = init_stock

        # Извлечение периода из period_label
        period_text = self.period_label.text().replace("Период анализа: ", "")

        dialog = StockValueAnalysisDialog(
            self,
            movement_data=self.movement_data_by_code,
            filtered_codes=filtered_codes,
            price_by_code=price_by_code,
            initial_stock_by_code=initial_stock_by_code,
            period_text=period_text
        )
        dialog.exec()