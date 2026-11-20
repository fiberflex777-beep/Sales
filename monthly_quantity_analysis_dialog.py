from base_monthly_analysis_dialog import BaseMonthlyAnalysisDialog

class MonthlyQuantityAnalysisDialog(BaseMonthlyAnalysisDialog):
    """Диалог для помесячного анализа продаж в штуках"""

    def __init__(self, parent=None, movement_data_by_code=None, filtered_codes=None):
        super().__init__(parent, movement_data_by_code, filtered_codes)

    def get_window_title(self) -> str:
        return "Помесячный анализ в штуках"

    def get_ylabel(self) -> str:
        return "Количество продаж (шт)"

    def get_title_all_years(self) -> str:
        return "Помесячные продажи (усреднено за все года)"

    def get_title_single_year(self, year: int) -> str:
        return f"Помесячные продажи за {year} год"

    def prepare_data(self):
        """Заполняет self._monthly_data словарём {(год, месяц): суммарные продажи в штуках}"""
        monthly_data = {}
        for code, movements in self.movement_data_by_code.items():
            if self.filtered_codes_set and code not in self.filtered_codes_set:
                continue
            for date, _, outgoing in movements:
                key = (date.year, date.month)
                monthly_data[key] = monthly_data.get(key, 0) + outgoing
        self._monthly_data = monthly_data

    def _format_total(self, value):
        """Форматирование общего количества продаж (целые числа с пробелами-разделителями тысяч)."""
        return f"{int(value):,}".replace(',', ' ')

    def _format_percent(self, value):
        """Форматирование процента с одним знаком после запятой."""
        return f"{value:+.1f}%"