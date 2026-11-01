"""Custom theme editor dialog."""
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QColorDialog, QDialog, QDialogButtonBox, QGridLayout,
                             QLabel, QPushButton, QVBoxLayout)


class ThemeEditor(QDialog):
    """Edit a draft palette; changes are applied only after saving."""
    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setWindowTitle('自訂配色')
        self.setMinimumWidth(440)
        self.colors = dict(colors)
        self.color_buttons = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        layout.addWidget(QLabel('選擇你喜歡的顏色組合'))
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        for row, (key, label) in enumerate((('bg', '視窗背景'), ('panel', '面板'), ('text', '文字'),
                                            ('accent', '重點顏色'), ('output', '輸出欄'))):
            grid.addWidget(QLabel(label), row, 0)
            button = QPushButton()
            button.setMinimumWidth(150)
            button.setObjectName('color-' + key)
            button.clicked.connect(lambda checked=False, k=key: self.pick_color(k))
            grid.addWidget(button, row, 1)
            self.color_buttons[key] = button
        layout.addLayout(grid)
        self.preview = QLabel('配色預覽     文字與輸出內容')
        self.preview.setMinimumHeight(54)
        self.preview.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('儲存並套用')
        buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.update_preview()

    def pick_color(self, key):
        selected = QColorDialog.getColor(QColor(self.colors[key]), self, '選擇顏色', options=QColorDialog.DontUseNativeDialog)
        if selected.isValid():
            self.colors[key] = selected.name()
            self.update_preview()

    def update_preview(self):
        for key, button in self.color_buttons.items():
            color = self.colors[key]
            fg = '#ffffff' if QColor(color).lightness() < 128 else '#181818'
            button.setText(color.upper())
            button.setStyleSheet(f'QPushButton {{ background: {color}; color: {fg}; border: 1px solid #888888; border-radius: 5px; padding: 8px 12px; }}')
        c = self.colors
        self.preview.setStyleSheet(f"background: {c['output']}; color: {c['text']}; border: 1px solid {c['accent']}; border-radius: 5px; padding: 8px;")
