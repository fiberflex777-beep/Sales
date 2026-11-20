# monthly_sum_analysis_dialog.py
from base_monthly_analysis_dialog import BaseMonthlyAnalysisDialog


class MonthlySumAnalysisDialog(BaseMonthlyAnalysisDialog):
    """Диалог для помесячного анализа продаж в денежном выражении"""

    def __init__(self, parent=None, movement_data_by_code=None, filtered_codes=None, price_by_code=None):
        self.price_by_code = price_by_code or {}
        super().__init__(parent, movement_data_by_code, filtered_codes)

    def get_window_title(self) -> str:
        return "Помесячный анализ в сумме"

    def get_ylabel(self) -> str:
        return "Сумма продаж (руб)"

    def get_title_all_years(self) -> str:
        return "Помесячный анализ в сумме (усреднено за все года)"

    def get_title_single_year(self, year: int) -> str:
        return f"Помесячный анализ в сумме за {year} год"

    def prepare_data(self):
        monthly_data = {}
        for code, movements in self.movement_data_by_code.items():
            if self.filtered_codes_set and code not in self.filtered_codes_set:
                continue
            price = self.price_by_code.get(code, 0.0)
            for date, _, outgoing in movements:
                amount = outgoing * price
                key = (date.year, date.month)
                monthly_data[key] = monthly_data.get(key, 0) + amount
        self._monthly_data = monthly_data

    # Переопределение методов форматирования для сумм
    def _format_total(self, value):
        """Форматирование общей суммы с двумя знаками после запятой и разделителями тысяч."""
        return f"{value:,.2f}".replace(',', ' ').replace('.', ',')

    def _format_percent(self, value):
        """Форматирование процента с одним знаком после запятой и знаком +/‑."""
        return f"{value:+.1f}%"