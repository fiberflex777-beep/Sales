# plot_utils.py
"""Утилиты для работы с графиками matplotlib"""

import matplotlib
from matplotlib.figure import Figure

def create_empty_graph_message(message: str) -> Figure:
    """
    Создаёт фигуру matplotlib с текстовым сообщением (для случаев отсутствия данных).

    Args:
        message: Текст сообщения для отображения на графике.

    Returns:
        Figure: объект фигуры с настроенными осями.
    """
    matplotlib.use('QtAgg')
    fig = Figure(figsize=(12, 8), facecolor='white')
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, message,
            horizontalalignment='center', verticalalignment='center',
            transform=ax.transAxes, fontsize=14)
    ax.set_xticks([])
    ax.set_yticks([])
    return fig