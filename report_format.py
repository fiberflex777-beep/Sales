# report_format.py
"""
Единое описание формата входного Excel-отчёта о продажах.

Ранее индексы колонок и строки заголовков были «зашиты» магическими числами
в workers.py и mainwindow_data.py. Здесь они собраны в одном месте:
при изменении формата отчёта править нужно только этот файл.
"""

# Индекс ячейки с текстом периода анализа (строка, колонка) — 0-based
PERIOD_CELL = (4, 4)

# Минимальные размеры raw_df, чтобы период был доступен
MIN_ROWS_FOR_PERIOD = PERIOD_CELL[0] + 1
MIN_COLS_FOR_PERIOD = PERIOD_CELL[1] + 1

# Отображение имён выходных колонок на индексы колонок входного файла (0-based)
SOURCE_COLUMNS = {
    'Код': 0,
    'Арт': 3,
    'Наименование': 5,
    'Начальный остаток': 6,
    'Приход': 7,
    'Расход': 8,
    'Конечный остаток': 9,
    'Цена': 10,
    'Категория товара': 11,
}

# Колонка raw_df, содержащая текст документа движения
MOVEMENT_DOC_COL = 5
# Колонки raw_df с количеством прихода/расхода по документу
MOVEMENT_INCOMING_COL = 7
MOVEMENT_OUTGOING_COL = 8
# Количество первых колонок, которые должны быть пусты в строке-движении
MOVEMENT_EMPTY_PREFIX_COLS = 5

# Ключевые слова типов документов движения
INCOMING_DOC_KEYWORDS = ('Приходная накл.',)
OUTGOING_DOC_KEYWORDS = ('Расходная накл.',)
RETURN_DOC_KEYWORDS = ('Возврат',)

# Маркер продолжения строки движения (код в первой колонке начинается с него)
CONTINUATION_MARKER = '|'


def classify_document(doc_text: str):
    """Возвращает тип документа ('Расходная'/'Приходная'/'Возврат'/'Документ') или None."""
    if any(kw in doc_text for kw in OUTGOING_DOC_KEYWORDS):
        return "Расходная"
    if any(kw in doc_text for kw in INCOMING_DOC_KEYWORDS):
        return "Приходная"
    if any(kw in doc_text for kw in RETURN_DOC_KEYWORDS):
        return "Возврат"
    return None


def is_movement_document(doc_text: str) -> bool:
    """True, если текст ячейки похож на документ движения товара."""
    return classify_document(doc_text) is not None
