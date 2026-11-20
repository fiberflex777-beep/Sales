# workers.py
import re
from datetime import datetime, timedelta
from PyQt6.QtCore import QThread, pyqtSignal

import report_format as fmt


class CalculationWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(object, object, object)
    error = pyqtSignal(str)
    canceled = pyqtSignal()

    def __init__(self, raw_df, headers_row_index, original_data, settings, user_orders=None):
        super().__init__()
        self.raw_df = raw_df
        self.headers_row_index = headers_row_index
        self.original_data = original_data
        self.settings = settings
        self.user_orders = user_orders if user_orders is not None else {}
        self._is_canceled = False
        self._pd = None
        self._np = None

    @property
    def pd(self):
        """Ленивая загрузка pandas"""
        if self._pd is None:
            import pandas as pd
            self._pd = pd
        return self._pd

    @property
    def np(self):
        """Ленивая загрузка numpy"""
        if self._np is None:
            import numpy as np
            self._np = np
        return self._np

    def safe_float_convert(self, value, default=0.0):
        """Безопасное преобразование в float"""
        if self.pd.isna(value) or value == '' or value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _extract_period_dates(self):
        """Извлекает начальную и конечную даты периода из текста (ячейка E5)"""
        pd = self.pd
        period_text = "Не найден"
        if (len(self.raw_df) > fmt.MIN_ROWS_FOR_PERIOD
                and self.raw_df.shape[1] > fmt.MIN_COLS_FOR_PERIOD):
            raw_period_val = self.raw_df.iloc[fmt.PERIOD_CELL]
            if pd.notna(raw_period_val):
                period_text = str(raw_period_val).strip()

        dates_part = period_text.split(" - ")
        if len(dates_part) != 2:
            # Если не удалось распарсить, берём последние 90 дней
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=90)
        else:
            start_str, end_str = dates_part
            try:
                start_date = datetime.strptime(start_str, '%d.%m.%Y').date()
                end_date = datetime.strptime(end_str, '%d.%m.%Y').date()
            except ValueError:
                try:
                    start_date = datetime.strptime(start_str, '%d.%m.%y').date()
                    end_date = datetime.strptime(end_str, '%d.%m.%y').date()
                except ValueError:
                    end_date = datetime.now().date()
                    start_date = end_date - timedelta(days=90)
        return start_date, end_date

    def _extract_movement_data(self):
        """
        Собирает данные движения товаров по кодам.
        Возвращает:
          movement_data_by_code: {code: [(date, incoming, outgoing), ...]} – для расчётов
          movement_details_by_code: {code: [{'date':date, 'doc_type':str, 'doc_full':str,
                                             'counterparty':str, 'incoming':float, 'outgoing':float}, ...]} – для детализации
        """
        pd = self.pd
        movement_data_by_code = {}
        movement_details_by_code = {}
        movement_df = self.raw_df.iloc[self.headers_row_index + 1:].reset_index(drop=True)
        date_pattern = r'(\d{2}\.\d{2}\.\d{2})'

        current_code = None
        for idx, row in movement_df.iterrows():
            if self._is_canceled:
                return None, None

            # Проверяем наличие кода в первой колонке
            code_val = row.iloc[0] if len(row) > 0 else None
            if pd.notna(code_val) and str(code_val) != '' and not str(code_val).startswith(fmt.CONTINUATION_MARKER):
                current_code = str(code_val)
                if current_code not in movement_data_by_code:
                    movement_data_by_code[current_code] = []
                    movement_details_by_code[current_code] = []

            elif current_code:
                # Проверяем, что первые N колонок пусты (это строка движения)
                first_empty = all(pd.isna(row.iloc[i]) or str(row.iloc[i]).strip() == ''
                                  for i in range(fmt.MOVEMENT_EMPTY_PREFIX_COLS) if i < len(row))
                sixth_col = row.iloc[fmt.MOVEMENT_DOC_COL] if len(row) > fmt.MOVEMENT_DOC_COL else None
                doc_type = fmt.classify_document(str(sixth_col)) if pd.notna(sixth_col) else None
                is_movement_doc = doc_type is not None

                if first_empty and is_movement_doc:
                    cell_val = sixth_col
                    if pd.notna(cell_val):
                        # Ищем дату в ячейке
                        matches = re.findall(date_pattern, str(cell_val))
                        if matches:
                            try:
                                date_str = matches[0]
                                date_found = datetime.strptime(date_str, '%d.%m.%y').date()

                                doc_text = str(cell_val)

                                # Извлекаем контрагента (часть после точки с запятой)
                                counterparty = ""
                                if ';' in doc_text:
                                    parts = doc_text.split(';', 1)
                                    if len(parts) > 1:
                                        counterparty = parts[1].strip()

                                incoming_qty_raw = row.iloc[fmt.MOVEMENT_INCOMING_COL] if len(row) > fmt.MOVEMENT_INCOMING_COL else None
                                outgoing_qty_raw = row.iloc[fmt.MOVEMENT_OUTGOING_COL] if len(row) > fmt.MOVEMENT_OUTGOING_COL else None

                                incoming_qty = self.safe_float_convert(incoming_qty_raw, 0.0)
                                outgoing_qty = self.safe_float_convert(outgoing_qty_raw, 0.0)

                                movement_data_by_code[current_code].append((date_found, incoming_qty, outgoing_qty))
                                movement_details_by_code[current_code].append({
                                    'date': date_found,
                                    'doc_type': doc_type,
                                    'doc_full': doc_text,
                                    'counterparty': counterparty,
                                    'incoming': incoming_qty,
                                    'outgoing': outgoing_qty
                                })
                            except ValueError:
                                continue
        return movement_data_by_code, movement_details_by_code

    def _calculate_sales_data(self, movement_data_by_code, start_date, end_date):
        """
        Рассчитывает для каждого товара:
        - среднюю продажу в дни с ненулевым остатком
        - общее количество продаж
        - количество дней с продажами
        - количество дней с ненулевым остатком
        """
        pd = self.pd
        sales_data_by_code = {}
        total_codes = len(movement_data_by_code)

        # Предварительно создаём словарь начальных остатков для быстрого доступа
        # (векторизованно, без построчного iterrows)
        initial_stock_map = {}
        if 'Код' in self.original_data.columns:
            codes = self.original_data['Код'].astype(str)
            stocks = pd.to_numeric(self.original_data['Начальный остаток'], errors='coerce').fillna(0.0)
            initial_stock_map = dict(zip(codes, stocks))

        for i, (code, records) in enumerate(movement_data_by_code.items()):
            if self._is_canceled:
                return None

            # Начальный остаток для товара
            initial_stock = initial_stock_map.get(str(code), 0.0)

            # Агрегируем движения по дням (только в пределах периода)
            daily_movements = {}
            for date, incoming, outgoing in records:
                if start_date <= date <= end_date:
                    if date not in daily_movements:
                        daily_movements[date] = {'incoming': 0.0, 'outgoing': 0.0}
                    daily_movements[date]['incoming'] += incoming
                    daily_movements[date]['outgoing'] += outgoing

            # Вычисляем показатели, моделируя остаток день за днём
            total_outgoing = 0.0
            days_with_stock = 0
            days_with_sales = 0

            current_date = start_date
            current_stock = initial_stock
            while current_date <= end_date:
                day_outgoing = 0.0
                if current_date in daily_movements:
                    current_stock += daily_movements[current_date]['incoming']
                    day_outgoing = daily_movements[current_date]['outgoing']
                    current_stock -= day_outgoing
                    total_outgoing += day_outgoing

                if current_stock > 0:
                    days_with_stock += 1
                if day_outgoing > 0:
                    days_with_sales += 1

                current_date += timedelta(days=1)

            avg_sales = total_outgoing / days_with_stock if days_with_stock > 0 else 0.0

            sales_data_by_code[code] = {
                'avg_sales': avg_sales,
                'total_sales': total_outgoing,
                'days_with_stock': days_with_stock,
                'days_with_sales': days_with_sales
            }

            progress_value = int((i + 1) / total_codes * 100)
            self.progress.emit(progress_value)

        return sales_data_by_code

    def _apply_user_orders(self, df):
        """Применяет пользовательские заказы к DataFrame"""
        if not self.user_orders or 'Код' not in df.columns:
            return df

        code_series = df['Код'].astype(str)
        code_to_idx = {code: idx for idx, code in enumerate(code_series)}

        for code, order in self.user_orders.items():
            if code in code_to_idx:
                idx = code_to_idx[code]
                df.loc[idx, 'Заказ'] = order
                # Пересчитываем сумму
                price = df.loc[idx, 'Цена']
                df.loc[idx, 'Сумма'] = order * price
        return df

    def run(self):
        """Точка входа потока: гарантированно перехватывает любые исключения."""
        try:
            self._run_impl()
        except Exception as e:
            # Любая непредвиденная ошибка не должна «глушить» поток без сигнала.
            import traceback
            traceback.print_exc()
            self.error.emit(str(e))

    def _run_impl(self):
        if self.original_data is None or self.original_data.empty:
            self.error.emit("Нет данных для расчёта")
            return

        start_date, end_date = self._extract_period_dates()
        if self._is_canceled:
            self.canceled.emit()
            return

        movement_data_by_code, movement_details_by_code = self._extract_movement_data()
        if movement_data_by_code is None:
            self.canceled.emit()
            return

        sales_data_by_code = self._calculate_sales_data(movement_data_by_code, start_date, end_date)
        if sales_data_by_code is None:
            self.canceled.emit()
            return
        if self._is_canceled:
            self.canceled.emit()
            return

        pd = self.pd
        np = self.np
        df = self.original_data.copy()
        df['Код_стр'] = df['Код'].astype(str)

        df['Средняя продажа'] = df['Код_стр'].map(lambda x: sales_data_by_code.get(x, {}).get('avg_sales', 0.0))
        df['total_sales'] = df['Код_стр'].map(lambda x: sales_data_by_code.get(x, {}).get('total_sales', 0.0))
        df['days_with_sales'] = df['Код_стр'].map(lambda x: sales_data_by_code.get(x, {}).get('days_with_sales', 0))

        log_days = self.settings.get('log_days', 15)
        order_days = self.settings.get('order_days', 30)
        safety_days = self.settings.get('safety_days', 15)
        min_total_sales = self.settings.get('min_total_sales', 5)
        min_sales_days = self.settings.get('min_sales_days', 5)

        df['Лог. плечо (дни)'] = log_days
        df['Кол-во дней заказа'] = order_days

        df['Конечный остаток'] = pd.to_numeric(df['Конечный остаток'], errors='coerce').fillna(0)
        df['Цена'] = pd.to_numeric(df['Цена'], errors='coerce').fillna(0)

        df['Спрос за время доставки'] = log_days * df['Средняя продажа']
        df['Страховой запас'] = safety_days * df['Средняя продажа']
        df['Точка заказа'] = df['Спрос за время доставки'] + df['Страховой запас']
        df['Спрос за интервал'] = order_days * df['Средняя продажа']
        df['Целевой уровень'] = df['Точка заказа'] + df['Спрос за интервал']

        low_sales_condition = (df['total_sales'] < min_total_sales) | (df['days_with_sales'] < min_sales_days)

        conditions_status = [
            low_sales_condition,                                     # 1. Малые продажи
            df['Конечный остаток'] <= 0,                             # 2. Нет в наличии
            (df['Конечный остаток'] < df['Целевой уровень']) & (~low_sales_condition) & (df['Конечный остаток'] > 0),  # 3. Нужен заказ
            (df['Конечный остаток'] >= df['Целевой уровень']) & (~low_sales_condition) & (df['Конечный остаток'] > 0),  # 4. В достатке
        ]
        choices_status = [
            "Малые продажи",
            "Нет в наличии",
            "Нужен заказ",
            "В достатке",
        ]
        df['Статус заказа'] = np.select(conditions_status, choices_status, default="Нужен заказ")

        df['Оптимальный заказ'] = 0

        mask_order = (~low_sales_condition) & (df['Конечный остаток'] < df['Целевой уровень'])
        df.loc[mask_order, 'Оптимальный заказ'] = np.maximum(
            df.loc[mask_order, 'Целевой уровень'] - df.loc[mask_order, 'Конечный остаток'],
            0
        ).round().astype(int)

        df['Заказ'] = 0
        df['Сумма'] = 0.0

        df['Страховой запас'] = df['Страховой запас'].round().astype(int)
        df['Оптимальный заказ'] = df['Оптимальный заказ'].round().astype(int)
        df['Конечный остаток'] = df['Конечный остаток'].round().astype(int)
        df['Заказ'] = df['Заказ'].astype(int)

        df = self._apply_user_orders(df)

        cols_to_drop = [
            'Код_стр', 'total_sales', 'days_with_sales',
            'Спрос за время доставки', 'Точка заказа', 'Спрос за интервал'
        ]
        existing_cols = [col for col in cols_to_drop if col in df.columns]
        if existing_cols:
            df = df.drop(columns=existing_cols, errors='ignore')

        self.finished.emit(df, movement_data_by_code, movement_details_by_code)

    def cancel(self):
        self._is_canceled = True