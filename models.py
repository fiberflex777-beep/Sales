# models.py
import math
import pandas as pd
from PyQt6.QtCore import QAbstractTableModel, Qt, QModelIndex, pyqtSignal
from PyQt6.QtGui import QColor, QFont

DISPLAY_HEADER_MAP = {
    'Код': 'Код',
    'Наименование': 'Название',
    'Конечный остаток': 'Кон. остаток',
    'Начальный остаток': 'Нач. остаток',
    'Приход': 'Приход',
    'Расход': 'Расход',
    'Страховой запас': 'Страх. запас',
    'Оптимальный заказ': 'Оптим. заказ',
    'Заказ': 'Заказ',
    'Сумма': 'Сумма',
    'Средняя продажа': 'Ср. продажа',
    'Лог. плечо (дни)': 'Лог. плечо',
    'Кол-во дней заказа': 'Дней заказа',
    'Статус заказа': 'Статус',
    'Цена': 'Цена',
    'Категория товара': 'Категория',
    'Арт': 'Артикул',
}

def wrap_header_text(text):
    original_header = str(text)
    short_names = {
        'Средняя продажа': 'Ср. продажа',
        'Лог. плечо (дни)': 'Лог. плечо\n(дни)',
        'Кол-во дней заказа': 'Дней\nзаказа',
        'Страховой запас': 'Страх.\nзапас',
        'Оптимальный заказ': 'Оптим.\nзаказ',
        'Конечный остаток': 'Кон.\nостаток',
        'Начальный остаток': 'Нач.\nостаток',
        'Категория товара': 'Категория\nтовара'
    }
    if original_header in short_names:
        return short_names[original_header]
    return original_header


class PandasTableModel(QAbstractTableModel):
    totalSumChanged = pyqtSignal()

    STATUS_COLORS = {
        "Малые продажи": QColor(255, 218, 185),
        "Избыток": QColor(173, 216, 230),
        "В достатке": QColor(144, 238, 144),
        "Нужен заказ": QColor(255, 165, 0),
        "Нет в наличии": QColor(255, 99, 71),
    }
    BOLD_FONT = QFont()
    BOLD_FONT.setBold(True)
    NORMAL_FONT = QFont()

    def __init__(self, df=None):
        super().__init__()
        self._original_df = pd.DataFrame()
        self._display_indices = []
        self._filter_text = ""
        self._user_orders = {}
        self._code_to_original_index = {}
        self._cell_attrs_cache = {}
        self._cached_total_sum = 0.0
        self._total_sum_dirty = True
        self._columns = []
        self._code_col_idx = -1

        if df is not None:
            self.set_data(df)

    def set_data(self, df):
        self.beginResetModel()
        self._original_df = df.copy() if df is not None else pd.DataFrame()
        self._display_indices = list(range(len(self._original_df))) if not self._original_df.empty else []
        self._filter_text = ""
        self._user_orders.clear()
        self._cell_attrs_cache.clear()
        self._total_sum_dirty = True

        if not self._original_df.empty:
            self._columns = list(self._original_df.columns)
            if 'Код' in self._columns:
                self._code_col_idx = self._columns.index('Код')
                self._code_to_original_index = {
                    str(code): idx for idx, code in enumerate(self._original_df['Код'])
                }
            else:
                self._code_col_idx = -1
                self._code_to_original_index = {}
        else:
            self._columns = []
            self._code_col_idx = -1
            self._code_to_original_index = {}

        self.endResetModel()
        self.totalSumChanged.emit()

    def get_df(self):
        if self._original_df.empty or not self._display_indices:
            return pd.DataFrame()
        return self._original_df.iloc[self._display_indices].copy()

    def get_filtered_codes(self):
        if self._original_df.empty or not self._display_indices:
            return []
        codes = self._original_df.iloc[self._display_indices]['Код'].astype(str).tolist()
        return codes

    def get_user_orders(self):
        return self._user_orders.copy()

    def get_original_df(self):
        return self._original_df

    def get_total_sum(self):
        if self._total_sum_dirty:
            self._recalc_total_sum()
        return self._cached_total_sum

    def _recalc_total_sum(self):
        if self._original_df.empty or not self._display_indices:
            self._cached_total_sum = 0.0
            self._total_sum_dirty = False
            return

        total = 0.0
        if 'Цена' not in self._columns or 'Заказ' not in self._columns:
            self._cached_total_sum = 0.0
            self._total_sum_dirty = False
            return

        price_col_idx = self._columns.index('Цена')
        for orig_row in self._display_indices:
            code = str(self._original_df.iat[orig_row, self._code_col_idx])
            order = self._user_orders.get(code, self._original_df.iat[orig_row, self._columns.index('Заказ')])
            try:
                price = float(self._original_df.iat[orig_row, price_col_idx])
            except (ValueError, TypeError):
                price = 0.0
            try:
                order_val = float(order) if order not in (None, '') else 0.0
            except (ValueError, TypeError):
                order_val = 0.0
            total += order_val * price

        self._cached_total_sum = total
        self._total_sum_dirty = False

    def _save_user_order(self, code, order_value):
        if order_value == 0:
            self._user_orders.pop(code, None)
        else:
            self._user_orders[code] = order_value

    def _invalidate_cache_for_row(self, orig_row, col_names=None):
        if col_names is None:
            keys_to_remove = [key for key in self._cell_attrs_cache if key[0] == orig_row]
            for key in keys_to_remove:
                del self._cell_attrs_cache[key]
        else:
            for col in col_names:
                key = (orig_row, col)
                self._cell_attrs_cache.pop(key, None)

    def _update_row_order(self, orig_row, order):
        code = str(self._original_df.iat[orig_row, self._code_col_idx])
        self._save_user_order(code, order)
        if 'Заказ' in self._columns:
            order_col_idx = self._columns.index('Заказ')
            self._original_df.iat[orig_row, order_col_idx] = order
        if 'Цена' in self._columns and 'Сумма' in self._columns:
            price_col_idx = self._columns.index('Цена')
            sum_col_idx = self._columns.index('Сумма')
            try:
                price = float(self._original_df.iat[orig_row, price_col_idx])
            except (ValueError, TypeError):
                price = 0.0
            self._original_df.iat[orig_row, sum_col_idx] = order * price

    def batch_set_orders(self, orders_dict):
        if not orders_dict:
            return

        affected_orig_rows = set()
        for code, order in orders_dict.items():
            if code in self._code_to_original_index:
                orig_row = self._code_to_original_index[code]
                affected_orig_rows.add(orig_row)
                self._update_row_order(orig_row, order)

        if not affected_orig_rows:
            return

        for orig_row in affected_orig_rows:
            self._invalidate_cache_for_row(orig_row, col_names=['Заказ', 'Сумма'])

        self._total_sum_dirty = True

        display_rows = []
        for i, orig_row in enumerate(self._display_indices):
            if orig_row in affected_orig_rows:
                display_rows.append(i)

        if display_rows:
            min_row = min(display_rows)
            max_row = max(display_rows)
            col_order = self._get_column_index('Заказ')
            col_sum = self._get_column_index('Сумма')
            if col_order != -1:
                top_left = self.createIndex(min_row, col_order)
                bottom_right = self.createIndex(max_row, col_order)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.EditRole])
            if col_sum != -1:
                top_left = self.createIndex(min_row, col_sum)
                bottom_right = self.createIndex(max_row, col_sum)
                self.dataChanged.emit(top_left, bottom_right, [Qt.ItemDataRole.EditRole])

        self.totalSumChanged.emit()

    def filter_data(self, filter_text):
        self._filter_text = filter_text.lower() if filter_text else ""
        self.beginResetModel()
        if not self._filter_text or self._original_df.empty:
            self._display_indices = list(range(len(self._original_df)))
        else:
            mask = pd.Series(False, index=self._original_df.index)
            if 'Код' in self._original_df.columns:
                mask |= self._original_df['Код'].astype(str).str.lower().str.contains(self._filter_text, na=False)
            if 'Арт' in self._original_df.columns:
                mask |= self._original_df['Арт'].astype(str).str.lower().str.contains(self._filter_text, na=False)
            if 'Наименование' in self._original_df.columns:
                mask |= self._original_df['Наименование'].astype(str).str.lower().str.contains(self._filter_text, na=False)
            self._display_indices = self._original_df.index[mask].tolist()

        self._total_sum_dirty = True
        self.endResetModel()
        self.totalSumChanged.emit()

    def sort(self, column_index, order=Qt.SortOrder.AscendingOrder):
        if self._original_df.empty or column_index >= len(self._columns):
            return
        col_name = self._columns[column_index]
        ascending = (order == Qt.SortOrder.AscendingOrder)

        values = self._original_df.iloc[self._display_indices][col_name]

        try:
            numeric_series = pd.to_numeric(values, errors='coerce')
            if not numeric_series.isna().all():
                sorted_idx = numeric_series.argsort()
                if not ascending:
                    sorted_idx = sorted_idx[::-1]
                self._display_indices = [self._display_indices[i] for i in sorted_idx]
            else:
                sorted_idx = values.astype(str).argsort()
                if not ascending:
                    sorted_idx = sorted_idx[::-1]
                self._display_indices = [self._display_indices[i] for i in sorted_idx]
        except (TypeError, ValueError):
            df_view = self._original_df.iloc[self._display_indices]
            sorted_df = df_view.sort_values(by=col_name, ascending=ascending, na_position='last')
            self._display_indices = sorted_df.index.tolist()

        self._total_sum_dirty = True
        self.layoutChanged.emit()
        self.totalSumChanged.emit()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._display_indices)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._columns)

    # --- ОПТИМИЗАЦИЯ: фильтруем роли, чтобы не лазить в кэш лишний раз ---
    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        # Если роль не входит в список поддерживаемых, сразу возвращаем None
        supported_roles = (
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.TextAlignmentRole,
            Qt.ItemDataRole.BackgroundRole,
            Qt.ItemDataRole.FontRole,
            Qt.ItemDataRole.ForegroundRole,
            Qt.ItemDataRole.EditRole
        )
        if role not in supported_roles:
            return None

        row, col = index.row(), index.column()
        if row < 0 or row >= self.rowCount() or col < 0 or col >= self.columnCount():
            return None

        orig_row = self._display_indices[row]
        col_name = self._columns[col]

        cache_key = (orig_row, col_name)

        if cache_key not in self._cell_attrs_cache:
            self._compute_cell_attrs(orig_row, col_name)

        cached = self._cell_attrs_cache[cache_key]
        return cached.get(role, None)
    # --------------------------------------------------------------------

    def _compute_cell_attrs(self, orig_row, col_name):
        col_idx = self._columns.index(col_name)
        value = self._original_df.iat[orig_row, col_idx]

        if col_name == 'Заказ':
            code = str(self._original_df.iat[orig_row, self._code_col_idx])
            value = self._user_orders.get(code, value)

        cache_entry = {}

        # ---- DisplayRole ----
        if value is None or (isinstance(value, float) and math.isnan(value)):
            formatted = ""
        else:
            if col_name in ['Заказ', 'Конечный остаток', 'Начальный остаток',
                           'Приход', 'Расход', 'Страховой запас', 'Оптимальный заказ']:
                try:
                    float_val = float(value)
                    if float_val == 0:
                        formatted = ""
                    else:
                        formatted = str(int(float_val))
                except (ValueError, TypeError):
                    formatted = str(value)
            elif col_name == 'Сумма':
                try:
                    float_val = float(value)
                    if float_val == 0:
                        formatted = ""
                    else:
                        formatted = f"{float_val:,.2f}".replace(',', ' ').replace('.', ',')
                except (ValueError, TypeError):
                    formatted = str(value)
            elif col_name == 'Средняя продажа':
                try:
                    float_val = float(value)
                    if float_val == 0:
                        formatted = "0"
                    else:
                        formatted = f"{float_val:.3f}"
                except (ValueError, TypeError):
                    formatted = str(value)
            else:
                formatted = str(value)

        cache_entry[Qt.ItemDataRole.DisplayRole] = formatted

        # ---- TextAlignmentRole ----
        if col_name == 'Наименование':
            cache_entry[Qt.ItemDataRole.TextAlignmentRole] = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        else:
            cache_entry[Qt.ItemDataRole.TextAlignmentRole] = Qt.AlignmentFlag.AlignCenter

        # ---- BackgroundRole ----
        if col_name == 'Заказ':
            cache_entry[Qt.ItemDataRole.BackgroundRole] = QColor(255, 255, 200)
        elif col_name == 'Статус заказа' and pd.notna(value):
            status_str = str(value)
            color = self.STATUS_COLORS.get(status_str)
            if color:
                cache_entry[Qt.ItemDataRole.BackgroundRole] = color

        # ---- FontRole ----
        if col_name in ('Конечный остаток', 'Оптимальный заказ'):
            cache_entry[Qt.ItemDataRole.FontRole] = self.BOLD_FONT

        # ---- ForegroundRole ----
        if col_name == 'Оптимальный заказ':
            cache_entry[Qt.ItemDataRole.ForegroundRole] = QColor(0, 128, 0)

        self._cell_attrs_cache[(orig_row, col_name)] = cache_entry

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                if section < 0 or section >= self.columnCount():
                    return None
                original_header = str(self._columns[section])
                wrapped_header = wrap_header_text(original_header)
                display_header = DISPLAY_HEADER_MAP.get(original_header, wrapped_header)
                return display_header
            else:
                return str(section + 1)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        flags = super().flags(index)
        col_name = self._columns[index.column()]
        if col_name == 'Заказ':
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False

        col_name = self._columns[index.column()]
        if col_name != 'Заказ':
            return False

        row = index.row()
        orig_row = self._display_indices[row]
        try:
            new_order = int(value) if value not in (None, '') else 0
        except ValueError:
            new_order = 0

        self._update_row_order(orig_row, new_order)

        self._invalidate_cache_for_row(orig_row, col_names=['Заказ', 'Сумма'])

        self._total_sum_dirty = True

        col_sum = self._get_column_index('Сумма')
        if col_sum != -1:
            self.dataChanged.emit(index, index, [role])
            sum_index = self.createIndex(row, col_sum)
            self.dataChanged.emit(sum_index, sum_index, [role])
        else:
            self.dataChanged.emit(index, index, [role])

        self.totalSumChanged.emit()
        return True

    def _get_column_index(self, col_name):
        if col_name in self._columns:
            return self._columns.index(col_name)
        return -1

    def get_total_stock_value(self):
        if self._original_df.empty or not self._display_indices:
            return 0.0

        if 'Конечный остаток' not in self._columns or 'Цена' not in self._columns:
            return 0.0

        end_stock_idx = self._columns.index('Конечный остаток')
        price_idx = self._columns.index('Цена')
        total = 0.0

        for orig_row in self._display_indices:
            end_stock = self._original_df.iat[orig_row, end_stock_idx]
            price = self._original_df.iat[orig_row, price_idx]

            try:
                end_val = float(end_stock) if end_stock not in (None, '') else 0.0
            except (ValueError, TypeError):
                end_val = 0.0

            try:
                price_val = float(price) if price not in (None, '') else 0.0
            except (ValueError, TypeError):
                price_val = 0.0

            total += end_val * price_val

        return total