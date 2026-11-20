# table_manager.py
from typing import cast, Optional
from PyQt6.QtWidgets import (
    QTableView, QHeaderView, QFrame, QVBoxLayout,
    QStyledItemDelegate, QLineEdit, QMenu
)
from PyQt6.QtCore import Qt, QEvent, QPoint
from PyQt6.QtGui import QIntValidator, QKeyEvent

from models import PandasTableModel


class CustomTableView(QTableView):
    """Таблица с запуском редактирования по Enter и Num Enter"""
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            index = self.currentIndex()
            if index.isValid() and (index.flags() & Qt.ItemFlag.ItemIsEditable):
                self.edit(index)
                return
        super().keyPressEvent(event)


class OrderDelegate(QStyledItemDelegate):
    """Делегат для колонки 'Заказ' с обработкой Enter для перехода вниз"""

    def __init__(self, parent=None, view=None):
        super().__init__(parent)
        self.view = view

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QIntValidator(0, 1_000_000, editor))
        editor.installEventFilter(self)
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.SubmitModelCache)
                if self.view:
                    current_index = self.view.currentIndex()
                    if current_index.isValid() and current_index.row() + 1 < self.view.model().rowCount():
                        next_index = self.view.model().index(current_index.row() + 1, current_index.column())
                        self.view.setCurrentIndex(next_index)
                return True
            elif key == Qt.Key.Key_Escape:
                self.closeEditor.emit(editor, QStyledItemDelegate.EndEditHint.RevertModelCache)
                return True
        return super().eventFilter(editor, event)

    def setEditorData(self, editor, index):
        line_edit = cast(QLineEdit, editor)
        value = index.data(Qt.ItemDataRole.DisplayRole)
        line_edit.setText(str(value) if value else "")

    def setModelData(self, editor, model, index):
        line_edit = cast(QLineEdit, editor)
        value = line_edit.text()
        if value:
            try:
                int_val = int(value)
                model.setData(index, int_val, Qt.ItemDataRole.EditRole)
            except ValueError:
                pass
        else:
            model.setData(index, 0, Qt.ItemDataRole.EditRole)


class TableManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.table = CustomTableView()
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableView.EditTrigger.DoubleClicked)
        self.table.verticalHeader().setVisible(False)

        # --- Оптимизация прокрутки ---
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        # ------------------------------

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        font = self.table.font()
        font.setPointSize(9)
        self.table.setFont(font)

        h_header = self.table.horizontalHeader()
        h_header.setFixedHeight(25)
        h_header.setStretchLastSection(False)

        v_header = self.table.verticalHeader()
        v_header.setDefaultSectionSize(22)

        self.table_frame = QFrame()
        self.table_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.table_frame.setLayout(layout)

        self._model: Optional[PandasTableModel] = None
        self._delegate = OrderDelegate(self.table, view=self.table)

    def set_model(self, model: Optional[PandasTableModel]):
        self._model = model
        self.table.setModel(model)

        if model and 'Заказ' in model.get_df().columns:
            col_index = model.get_df().columns.get_loc('Заказ')
            self.table.setItemDelegateForColumn(col_index, self._delegate)

        if model:
            model.dataChanged.connect(self._on_model_data_changed)

        self._setup_columns()

        if self._model:
            selection_model = self.table.selectionModel()
            selection_model.currentChanged.connect(
                self.main_window.on_table_selection_changed
            )

        if self._model and self._model.rowCount() > 0:
            self.table.selectRow(0)

    def _show_context_menu(self, pos: QPoint):
        index = self.table.indexAt(pos)
        if index.isValid():
            menu = QMenu()
            action = menu.addAction("Показать движения")
            action.triggered.connect(lambda: self.main_window.show_movement_details(index))
            menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_model_data_changed(self, _top_left, _bottom_right, _roles):
        self.main_window.update_total_sum()

    def _setup_columns(self):
        if self._model is None:
            return

        df = self._model.get_df()
        if df.empty:
            return

        header = self.table.horizontalHeader()
        header.setMinimumSectionSize(30)
        header.setDefaultSectionSize(60)

        max_art_len = 0
        if 'Арт' in df.columns:
            art_series = df['Арт'].astype(str)
            if not art_series.empty:
                max_art_len = art_series.str.len().max()

        for col_idx, col_name in enumerate(df.columns):
            if col_name == 'Наименование':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Stretch)
            elif col_name == 'Статус заказа':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 120)
            elif col_name == 'Конечный остаток':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 90)
            elif col_name == 'Оптимальный заказ':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 90)
            elif col_name == 'Сумма':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 80)
            elif col_name == 'Код':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 60)
            elif col_name == 'Цена':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 70)
            elif col_name == 'Средняя продажа':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 90)
            elif col_name == 'Страховой запас':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 90)
            elif col_name == 'Арт':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                if max_art_len > 20:
                    art_width = 200
                elif max_art_len > 15:
                    art_width = 150
                elif max_art_len > 10:
                    art_width = 120
                else:
                    art_width = 100
                self.table.setColumnWidth(col_idx, min(art_width, 250))
            elif col_name == 'Категория товара':
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 75)
            else:
                header.setSectionResizeMode(col_idx, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col_idx, 70)

        hide_cols = ['Лог. плечо (дни)', 'Кол-во дней заказа', 'Начальный остаток', 'Приход', 'Расход', 'Целевой уровень']
        for col_name in hide_cols:
            if col_name in df.columns:
                col_idx = df.columns.get_loc(col_name)
                self.table.setColumnHidden(col_idx, True)

    def get_current_table_data(self):
        if self._model is None:
            return self.main_window.original_data.copy()
        return self._model.get_df().copy()

    def get_selected_code(self):
        selection_model = self.table.selectionModel()
        if selection_model.hasSelection():
            index = selection_model.selectedRows()[0]
            code_index = self._model.index(index.row(), 0)
            return code_index.data(Qt.ItemDataRole.DisplayRole)
        return None

    def refresh_table(self):
        if self._model is not None:
            self._model.layoutChanged.emit()