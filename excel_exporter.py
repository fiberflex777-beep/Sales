# excel_exporter.py
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from typing import Dict, List, Any


# ----------------------------------------------------------------------
# Общие стили и вспомогательные функции
# ----------------------------------------------------------------------

PRODUCT_FONT = Font(size=10)
MOVEMENT_FONT = Font(size=9)
PRODUCT_FILL = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
MOVEMENT_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)


def _should_skip_zero(col_name: str, value) -> bool:
    """
    Возвращает True, если для колонки col_name значение 0 должно быть пропущено.
    """
    zero_columns = {
        'Конечный остаток', 'Средняя продажа', 'Страховой запас',
        'Оптимальный заказ', 'Заказ', 'Сумма'
    }
    if col_name in zero_columns and isinstance(value, (int, float)) and value == 0:
        return True
    return False


def _get_alignment(col_name: str, wrap_text: bool = False) -> Alignment:
    """Возвращает выравнивание в зависимости от имени колонки."""
    if col_name == 'Наименование':
        return Alignment(horizontal='left', vertical='center', wrap_text=True)
    else:
        return Alignment(horizontal='center', vertical='center', wrap_text=wrap_text)


def _apply_cell_formatting(ws, row: int, col: int, value, col_name: str, is_product: bool = True):
    """
    Создаёт ячейку в листе ws на позиции (row, col) с заданным value,
    применяет к ней форматирование в зависимости от типа строки и имени колонки.
    """
    cell = ws.cell(row=row, column=col, value=value)

    # Шрифт и заливка
    if is_product:
        cell.font = PRODUCT_FONT
        cell.fill = PRODUCT_FILL
    else:
        cell.font = MOVEMENT_FONT
        cell.fill = MOVEMENT_FILL

    cell.border = THIN_BORDER
    cell.alignment = _get_alignment(col_name, wrap_text=True)  # перенос для наименования

    # Числовой формат
    if isinstance(value, (int, float)):
        if col_name in ('Сумма', 'Цена'):
            cell.number_format = '#,##0.00'
        elif col_name == 'Средняя продажа':
            cell.number_format = '#,##0.000'
        elif col_name in ('Приход', 'Расход', 'Начальный остаток', 'Конечный остаток',
                          'Страховой запас', 'Оптимальный заказ', 'Заказ'):
            cell.number_format = '0'
    return cell


# ----------------------------------------------------------------------
# Основная функция экспорта для согласования (с движениями)
# ----------------------------------------------------------------------

def export_order_to_excel(df: pd.DataFrame,
                          movement_details: Dict[str, List[Dict[str, Any]]],
                          file_path: str) -> None:
    """
    Сохраняет DataFrame с заказом в Excel, добавляя под каждой позицией
    свёрнутые группы строк с детальными движениями товара.

    Параметры:
        df: DataFrame с данными заказа (должен содержать колонки 'Код', 'Наименование',
            'Приход', 'Расход', 'Начальный остаток', 'Конечный остаток' и др.)
        movement_details: словарь {код товара: список движений}. Каждое движение –
            словарь с ключами 'date', 'doc_full', 'incoming', 'outgoing'.
        file_path: путь для сохранения файла.
    """
    # Переупорядочивание и фильтрация колонок согласно требованиям
    ordered_columns = [
        'Код', 'Арт', 'Наименование', 'Начальный остаток', 'Приход', 'Расход',
        'Конечный остаток', 'Цена', 'Категория товара', 'Средняя продажа',
        'Страховой запас', 'Оптимальный заказ', 'Заказ', 'Сумма'
    ]
    missing = set(ordered_columns) - set(df.columns)
    if missing:
        raise ValueError(f"В DataFrame отсутствуют необходимые колонки: {missing}")
    df = df[ordered_columns].copy()

    wb = Workbook()
    ws = wb.active
    ws.title = "Заказ"

    headers = list(df.columns)

    # ----------------------------------------------
    # 1. Заголовки
    # ----------------------------------------------
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = THIN_BORDER

    # ----------------------------------------------
    # 2. Запись данных
    # ----------------------------------------------
    current_row = 2  # начинаем со второй строки (после заголовка)

    for idx, row in df.iterrows():
        # ---- Запись строки товара ----
        for col_num, col_name in enumerate(headers, 1):
            value = row[col_name]
            if pd.isna(value) or _should_skip_zero(col_name, value):
                value = None
            _apply_cell_formatting(ws, current_row, col_num, value, col_name, is_product=True)

        # ---- Обработка движений для этого товара ----
        code = str(row['Код'])
        movements = movement_details.get(code, [])
        if movements:
            movements_sorted = sorted(movements, key=lambda x: x['date'])

            try:
                current_stock = float(row['Начальный остаток']) if pd.notna(row['Начальный остаток']) else 0.0
            except (ValueError, TypeError):
                current_stock = 0.0

            first_movement_row = current_row + 1

            for mov in movements_sorted:
                current_row += 1
                incoming = mov.get('incoming', 0.0)
                outgoing = mov.get('outgoing', 0.0)
                doc_full = mov.get('doc_full', '')

                start_stock = current_stock
                end_stock = start_stock + incoming - outgoing

                for col_num, col_name in enumerate(headers, 1):
                    value = None
                    if col_name == 'Наименование':
                        value = doc_full
                    elif col_name == 'Приход' and incoming > 0:
                        value = incoming
                    elif col_name == 'Расход' and outgoing > 0:
                        value = outgoing
                    elif col_name == 'Начальный остаток':
                        value = start_stock
                    elif col_name == 'Конечный остаток':
                        value = end_stock

                    if value is not None and _should_skip_zero(col_name, value):
                        value = None

                    _apply_cell_formatting(ws, current_row, col_num, value, col_name, is_product=False)

                current_stock = end_stock

            # Группируем строки движений (не включая строку товара)
            if first_movement_row <= current_row:
                ws.row_dimensions.group(first_movement_row, current_row, outline_level=1, hidden=True)

        # Переходим к следующему товару
        current_row += 1

    # ----------------------------------------------
    # 3. Фиксированная ширина колонок
    # ----------------------------------------------
    fixed_widths = {
        'Код': 12,
        'Арт': 12,
        'Наименование': 70,
        'Начальный остаток': 12,
        'Приход': 12,
        'Расход': 12,
        'Конечный остаток': 12,
        'Цена': 12,
        'Категория товара': 12,
        'Средняя продажа': 12,
        'Страховой запас': 12,
        'Оптимальный заказ': 12,
        'Заказ': 12,
        'Сумма': 12
    }
    for col_num, col_name in enumerate(headers, 1):
        col_letter = get_column_letter(col_num)
        ws.column_dimensions[col_letter].width = fixed_widths.get(col_name, 10)

    wb.save(file_path)


# ----------------------------------------------------------------------
# Функция экспорта для поставщика (без движений, только нужные колонки)
# ----------------------------------------------------------------------

def export_supplier_order_to_excel(df: pd.DataFrame, file_path: str) -> None:
    """
    Сохраняет DataFrame (колонки: Код, Арт, Наименование, Заказ) в Excel
    с применением единого форматирования (шрифты, заливка, границы, перенос текста).

    Параметры:
        df: DataFrame, содержащий как минимум колонки 'Код', 'Арт', 'Наименование', 'Заказ'.
        file_path: путь для сохранения файла.
    """
    required_cols = {'Код', 'Арт', 'Наименование', 'Заказ'}
    if not required_cols.issubset(df.columns):
        missing = required_cols - set(df.columns)
        raise ValueError(f"Для экспорта поставщика необходимы колонки: {missing}")

    wb = Workbook()
    ws = wb.active
    ws.title = "Заказ"

    headers = list(df.columns)

    # Заголовки
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = THIN_BORDER

    # Данные
    for row_idx, (_, row) in enumerate(df.iterrows(), start=2):
        for col_num, col_name in enumerate(headers, 1):
            value = row[col_name]
            # Для колонки Заказ можно пропускать нули (опционально)
            if col_name == 'Заказ' and (pd.isna(value) or value == 0):
                value = None
            _apply_cell_formatting(ws, row_idx, col_num, value, col_name, is_product=True)

    # Ширина колонок
    fixed_widths = {
        'Код': 12,
        'Арт': 12,
        'Наименование': 70,
        'Заказ': 12
    }
    for col_num, col_name in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(col_num)].width = fixed_widths.get(col_name, 10)

    wb.save(file_path)