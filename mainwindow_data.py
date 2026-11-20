# mainwindow_data.py
import re
import logging
from datetime import datetime

import pandas as pd
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QDialog
from PyQt6.QtCore import QObject

logger = logging.getLogger("app.data")

import report_format as fmt
from workers import CalculationWorker
from dialogs import ProgressDialog
from excel_exporter import export_order_to_excel, export_supplier_order_to_excel


class DataMixin(QObject):
    """Миксин с методами для работы с данными (загрузка, расчёт, сохранение)."""

    # ------------------------------------------------------------------
    # Работа с файлом и расчётами
    # ------------------------------------------------------------------
    def open_file(self):
        """Открывает файл отчёта и запускает расчёт"""
        pandas = self._get_pd()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Открыть файл отчета",
            "",
            "Excel Files (*.xls *.xlsx *.xlsm);;All Files (*)"
        )
        if not file_path:
            return

        try:
            self._ensure_managers_loaded()
            self._ensure_model_loaded()

            df_raw = pandas.read_excel(file_path, sheet_name=0, header=None, dtype=object)

            headers_row_index = self._find_headers_row(df_raw)
            if headers_row_index == -1:
                QMessageBox.warning(
                    self, "Ошибка",
                    "Не удалось найти строку с заголовками 'Код', 'Арт', 'Товар/Склад/Документ'."
                )
                return

            product_df, period_text = self._extract_product_data(df_raw, headers_row_index)
            if product_df.empty:
                QMessageBox.warning(self, "Ошибка", "Не удалось извлечь данные товаров из файла.")
                return

            self.raw_df = df_raw
            self.headers_row_index = headers_row_index
            self.period_label.setText(f"Период анализа: {period_text}")

            # При открытии нового файла пользовательских заказов нет – передаём пустой словарь
            self._start_calculation(self.raw_df, self.headers_row_index, product_df, user_orders={})

        except Exception as e:
            logger.exception("Ошибка загрузки файла отчёта")
            QMessageBox.critical(self, "Ошибка загрузки", f"Не удалось загрузить файл:\n{str(e)}")

    def _find_headers_row(self, df_raw):
        """Ищет строку с заголовками колонок"""
        pandas = self._get_pd()
        for i in range(len(df_raw)):
            row_values = df_raw.iloc[i].tolist()
            has_code = any(pandas.notna(val) and 'Код' in str(val) for val in row_values)
            has_art = any(pandas.notna(val) and 'Арт' in str(val) for val in row_values)
            has_name = any(
                pandas.notna(val) and (
                    'Товар/Склад/Документ' in str(val) or str(val).startswith('Товар')
                )
                for val in row_values
            )
            if has_code and has_art and has_name:
                return i
        return -1

    def _extract_product_data(self, df_raw, headers_row_index):
        """Извлекает данные товаров и период"""
        pandas = self._get_pd()

        headers = df_raw.iloc[headers_row_index].tolist()
        col_map = fmt.SOURCE_COLUMNS

        max_col_index = len(headers) - 1
        for col_name, idx in col_map.items():
            if idx > max_col_index:
                raise ValueError(f"Столбец '{col_name}' находится за пределами данных файла.")

        df_data = df_raw.iloc[headers_row_index + 1:].reset_index(drop=True)

        filtered_df = pandas.DataFrame()
        for col_name, idx in col_map.items():
            filtered_df[col_name] = df_data.iloc[:, idx]

        product_rows_df = filtered_df[filtered_df['Код'].notna()].copy()
        product_rows_df = product_rows_df.reset_index(drop=True)
        product_rows_df['Заказ'] = 0

        period_text = "Не найден"
        if len(df_raw) >= fmt.MIN_ROWS_FOR_PERIOD and df_raw.shape[1] >= fmt.MIN_COLS_FOR_PERIOD:
            raw_period_val = df_raw.iloc[fmt.PERIOD_CELL]
            if pandas.notna(raw_period_val):
                period_text = str(raw_period_val).strip()

        date_match = re.search(r'(\d{2}\.\d{2}\.\d{2})\s*-\s*(\d{2}\.\d{2}\.\d{2})', period_text)
        if date_match:
            start_str, end_str = date_match.groups()
            try:
                start_date_obj = datetime.strptime(start_str, '%d.%m.%y')
                end_date_obj = datetime.strptime(end_str, '%d.%m.%y')
                formatted_start = start_date_obj.strftime('%d.%m.%Y')
                formatted_end = end_date_obj.strftime('%d.%m.%Y')
                period_text = f"{formatted_start} - {formatted_end}"
            except ValueError:
                pass

        product_rows_df['Средняя продажа'] = 0.0
        product_rows_df['Лог. плечо (дни)'] = 0
        product_rows_df['Страховой запас'] = 0
        product_rows_df['Кол-во дней заказа'] = 0
        product_rows_df['Оптимальный заказ'] = 0
        product_rows_df['Статус заказа'] = "Не рассчитано"
        product_rows_df['Сумма'] = 0.0

        return product_rows_df, period_text

    def _start_calculation(self, raw_df, headers_row_index, product_df, user_orders=None):
        """Запускает поток расчёта с текущими настройками и пользовательскими заказами (если есть)"""
        from workers import CalculationWorker

        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.rejected.connect(self._on_cancel_calculation)

        # Сохраняем пользовательские заказы для восстановления после расчёта
        self._user_orders_before_recalc = user_orders if user_orders is not None else {}

        self.worker_thread = CalculationWorker(
            raw_df, headers_row_index, product_df, self.settings, user_orders
        )
        self.worker_thread.progress.connect(self.progress_dialog.progress_bar.setValue)
        self.worker_thread.finished.connect(self._on_calculation_finished)
        self.worker_thread.error.connect(self._on_calculation_error)
        self.worker_thread.canceled.connect(self._on_calculation_canceled)

        self.worker_thread.start()
        self.progress_dialog.show()

    # ИЗМЕНЁН: теперь принимает три аргумента (updated_data, movement_data, movement_details)
    def _on_calculation_finished(self, updated_data, movement_data, movement_details):
        """Завершение расчёта - обновление данных и UI"""
        self.progress_dialog.accept()
        if self.worker_thread:
            self.worker_thread.wait()
            self.worker_thread = None

        self.original_data = updated_data
        self.movement_data_by_code = movement_data
        self.movement_details_by_code = movement_details   # <-- НОВОЕ поле

        self._reorder_columns()

        self.model.set_data(self.original_data)

        # Восстанавливаем фильтр, если он был сохранён
        if self._saved_filter_text is not None:
            filter_text = self._saved_filter_text
            # Применяем фильтр к новой модели
            self.model.filter_data(filter_text)
            # Восстанавливаем текст в поле поиска
            self.search_line.setText(filter_text)
            self._saved_filter_text = None

        # Восстанавливаем пользовательские заказы, если они были
        if hasattr(self, '_user_orders_before_recalc') and self._user_orders_before_recalc:
            self.model.batch_set_orders(self._user_orders_before_recalc)
            self._user_orders_before_recalc = None

        if self.table_manager:
            self.table_manager.set_model(self.model)

        if not hasattr(self, '_search_connected'):
            self.search_line.textChanged.connect(self.on_search_changed)
            self._search_connected = True

        self.update_total_sum()
        self.update_total_stock_sum()
        self.statusBar().showMessage(
            f"Расчет завершен для {len(self.original_data)} записей."
        )

    def _reorder_columns(self):
        """Приводит порядок колонок к требуемому виду"""
        if self.original_data is None or self.original_data.empty:
            return

        desired_order = [
            'Код', 'Арт', 'Наименование', 'Категория товара', 'Цена',
            'Средняя продажа', 'Страховой запас',
            'Статус заказа', 'Конечный остаток', 'Оптимальный заказ',
            'Заказ', 'Сумма'
        ]

        existing_desired = [col for col in desired_order if col in self.original_data.columns]
        other_cols = [col for col in self.original_data.columns if col not in existing_desired]
        final_columns = existing_desired + other_cols
        self.original_data = self.original_data[final_columns]

    def _on_calculation_error(self, error_msg):
        """Обработка ошибки в потоке расчёта"""
        if self.progress_dialog:
            self.progress_dialog.reject()
        if self.worker_thread:
            self.worker_thread.wait()
            self.worker_thread = None
        QMessageBox.critical(
            self, "Ошибка расчета",
            f"Произошла ошибка при расчете:\n{error_msg}"
        )

    def _on_calculation_canceled(self):
        """Обработка отмены расчёта"""
        if self.progress_dialog:
            self.progress_dialog.reject()
        if self.worker_thread:
            self.worker_thread.wait()
            self.worker_thread = None
        self.statusBar().showMessage("Расчет отменен пользователем.")

    def _on_cancel_calculation(self):
        """Отмена расчёта по кнопке в диалоге"""
        if self.worker_thread:
            self.worker_thread.cancel()

    # ------------------------------------------------------------------
    # Действия с заказом
    # ------------------------------------------------------------------
    def clear_order(self):
        """Очищает заказ (устанавливает Заказ = 0, Сумма = 0) для всех отображаемых товаров"""
        if self.model is None or self.model.rowCount() == 0:
            QMessageBox.information(self, "Информация", "Нет данных для очистки.")
            return

        codes = self.model.get_filtered_codes()
        orders_dict = {code: 0 for code in codes}
        self.model.batch_set_orders(orders_dict)
        self.update_total_sum()
        self.statusBar().showMessage("Заказ очищен")

    def set_optimal_order(self):
        """Устанавливает оптимальный заказ в колонку Заказ для всех отображаемых товаров"""
        if self.model is None or self.model.rowCount() == 0:
            QMessageBox.information(self, "Информация", "Нет данных для установки оптимального заказа.")
            return

        display_df = self.model.get_df()
        # Векторизованно: без построчного iterrows
        orders_series = pd.to_numeric(display_df['Оптимальный заказ'], errors='coerce').fillna(0).astype(int)
        orders_dict = dict(zip(display_df['Код'].astype(str), orders_series))

        self.model.batch_set_orders(orders_dict)
        self.update_total_sum()
        self.statusBar().showMessage("Установлен оптимальный заказ")

    # ------------------------------------------------------------------
    # ИМПОРТ ЗАКАЗА ИЗ ФАЙЛА (НОВЫЙ МЕТОД)
    # ------------------------------------------------------------------
    def import_order_from_file(self):
        """Импортирует значения заказа из ранее сохранённого Excel-файла."""
        if self.model is None or self.original_data is None or self.original_data.empty:
            QMessageBox.warning(self, "Предупреждение", "Сначала загрузите данные отчёта.")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл с заказом",
            "",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        if not file_path:
            return

        try:
            pandas = self._get_pd()
            df_import = pandas.read_excel(file_path, sheet_name=0, dtype=str)  # читаем всё как строки для надёжности

            # Проверка наличия обязательных колонок
            required_cols = {'Код', 'Заказ'}
            if not required_cols.issubset(df_import.columns):
                missing = required_cols - set(df_import.columns)
                QMessageBox.warning(
                    self, "Ошибка формата",
                    f"В файле отсутствуют необходимые колонки: {', '.join(missing)}.\n"
                    "Файл должен содержать колонки 'Код' и 'Заказ'."
                )
                return

            # Формируем словарь {код: заказ} (векторизованно)
            codes = df_import['Код'].astype(str).str.strip()
            orders = pd.to_numeric(df_import['Заказ'], errors='coerce').fillna(0).astype(int)
            mask = codes.ne('') & codes.ne('nan') & codes.ne('None')
            orders_dict = dict(zip(codes[mask], orders[mask]))

            if not orders_dict:
                QMessageBox.information(self, "Импорт", "В файле не найдено ни одной записи с кодом товара.")
                return

            # Применяем пакетное обновление заказов
            self.model.batch_set_orders(orders_dict)

            # Обновляем отображение общей суммы (сигнал из модели должен сделать это автоматически)
            self.update_total_sum()

            QMessageBox.information(
                self, "Успех",
                f"Импортировано {len(orders_dict)} записей.\n"
                "Значения в колонке 'Заказ' обновлены."
            )
            self.statusBar().showMessage(f"Заказ импортирован из {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка импорта", f"Не удалось прочитать файл:\n{str(e)}")

    # ------------------------------------------------------------------
    # Сохранение заказа в Excel (ИЗМЕНЁН)
    # ------------------------------------------------------------------
    def save_order_to_excel(self):
        """Сохраняет текущие данные заказа в Excel с выбором режима."""
        if self.original_data is None or self.original_data.empty:
            QMessageBox.warning(self, "Предупреждение", "Нет данных для сохранения.")
            return

        # 1. Выбор режима
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Выберите режим сохранения")
        msg_box.setText("Для кого сохранить файл?")
        btn_approval = msg_box.addButton("Для согласования", QMessageBox.ButtonRole.ActionRole)
        btn_supplier = msg_box.addButton("Для поставщика", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        if msg_box.clickedButton() == btn_cancel:
            return

        # 2. Запрос пути к файлу
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить заказ в Excel",
            "",
            "Excel Files (*.xlsx);;All Files (*)"
        )
        if not file_path:
            return
        if not file_path.endswith('.xlsx'):
            file_path += '.xlsx'

        try:
            if msg_box.clickedButton() == btn_approval:
                # Режим "Для согласования" – используем текущую логику с движениями
                if self.table_manager:
                    current_data = self.table_manager.get_current_table_data()
                else:
                    current_data = self.original_data.copy()
                export_order_to_excel(current_data, self.movement_details_by_code, file_path)
                QMessageBox.information(self, "Успех", f"Заказ сохранён для согласования:\n{file_path}")

            else:  # btn_supplier
                # Режим "Для поставщика" – только колонки Код, Арт, Наименование, Заказ

                # Берём полные данные и применяем пользовательские заказы (векторизованно)
                full_df = self.original_data.copy()
                user_orders = self.model.get_user_orders() if self.model else {}

                if 'Код' in full_df.columns and user_orders:
                    codes_str = full_df['Код'].astype(str)
                    order_series = codes_str.map(user_orders)
                    has_user_order = order_series.notna()
                    full_df.loc[has_user_order, 'Заказ'] = order_series[has_user_order]
                    if 'Цена' in full_df.columns:
                        price = pd.to_numeric(full_df['Цена'], errors='coerce').fillna(0.0)
                        full_df.loc[has_user_order, 'Сумма'] = (
                            order_series[has_user_order] * price[has_user_order]
                        )

                # Фильтруем строки с заказом > 0 и выбираем нужные колонки
                if 'Арт' in full_df.columns:
                    supplier_df = full_df[full_df['Заказ'] > 0][['Код', 'Арт', 'Наименование', 'Заказ']]
                else:
                    # Если вдруг нет Арт, то пропускаем
                    supplier_df = full_df[full_df['Заказ'] > 0][['Код', 'Наименование', 'Заказ']]

                if supplier_df.empty:
                    QMessageBox.information(self, "Информация", "Нет товаров с заказом больше нуля.")
                    return

                # Используем новую функцию для сохранения с единым форматированием
                export_supplier_order_to_excel(supplier_df, file_path)
                QMessageBox.information(self, "Успех", f"Заказ для поставщика сохранён:\n{file_path}")

            self.statusBar().showMessage(f"Заказ сохранён в {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить файл:\n{str(e)}")

    # ------------------------------------------------------------------
    # Вспомогательный метод для получения текущих заказов
    # ------------------------------------------------------------------
    def _get_current_user_orders(self):
        """Возвращает словарь пользовательских заказов из текущей модели"""
        if self.model is not None:
            return self.model.get_user_orders()
        return {}

    # ------------------------------------------------------------------
    # Перерасчёт с новыми настройками
    # ------------------------------------------------------------------
    def recalculate_with_new_settings(self):
        """Перерасчёт с новыми настройками"""
        if self.raw_df is None or self.raw_df.empty or self.headers_row_index == -1:
            QMessageBox.warning(
                self, "Предупреждение",
                "Для перерасчета с новыми настройками необходимо заново загрузить файл."
            )
            return

        # Сохраняем текущий фильтр
        self._saved_filter_text = self.search_line.text()

        # Сохраняем текущие пользовательские заказы
        old_orders = self._get_current_user_orders()

        product_df, period_text = self._extract_product_data(self.raw_df, self.headers_row_index)
        self.period_label.setText(f"Период анализа: {period_text}")

        self._start_calculation(self.raw_df, self.headers_row_index, product_df, old_orders)