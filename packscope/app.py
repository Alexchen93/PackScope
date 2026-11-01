"""PackScope's Qt interface for managing Ubuntu software."""
import sys
import shlex
import json
import re
from datetime import datetime
from pathlib import Path
from PyQt5.QtCore import (QAbstractTableModel, QEvent, QLibraryInfo, QModelIndex, QObject, QSettings, QSortFilterProxyModel,
                          Qt, QThread, QTimer, QTranslator, pyqtSignal)
from PyQt5.QtGui import QColor, QFont, QIcon
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QFrame, QHBoxLayout, QHeaderView,
                             QLabel, QLineEdit, QMainWindow, QPushButton, QSplitter,
                             QTableView, QVBoxLayout, QWidget, QScrollArea, QDialog,
                             QDialogButtonBox, QFileDialog, QMessageBox, QPlainTextEdit,
                             QInputDialog, QProgressBar, QToolButton, QMenu, QComboBox,
                             QColorDialog, QGridLayout, QCheckBox, QTableWidget, QTableWidgetItem)
from packscope.inventory import scan_all
from packscope.inventory import Package
from packscope import actions, backend, launch

# Warm neutrals and restrained orange, informed by Ubuntu's colour palette.
DARK = {'bg':'#1b191b','panel':'#252225','surface':'#302b2c','text':'#f2eeeb','sub':'#c4b8b1',
        'border':'#49403e','accent':'#f29879','accenttext':'#231a18','selection':'#4a3431','output':'#111111'}
LIGHT = {'bg':'#f2f0ed','panel':'#fffdfa','surface':'#eee9e5','text':'#292321','sub':'#625956',
         'border':'#d9d1cb','accent':'#933f29','accenttext':'#ffffff','selection':'#f2ddd4','output':'#fffdfa'}

CUSTOM_KEYS = ('bg','panel','text','accent','output')


def mix_color(first, second, amount):
    a, b = QColor(first), QColor(second)
    return QColor(*(round(x * (1-amount) + y * amount) for x,y in zip(a.getRgb()[:3], b.getRgb()[:3]))).name()


def valid_custom_colors(value):
    if not isinstance(value, dict) or any(not isinstance(value.get(k), str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value[k]) for k in CUSTOM_KEYS):
        return None
    return {key:value[key].lower() for key in CUSTOM_KEYS}


def custom_palette(colors):
    c = dict(colors)
    c['surface'] = mix_color(c['bg'], c['panel'], .65)
    c['border'] = mix_color(c['panel'], c['text'], .24)
    c['sub'] = mix_color(c['text'], c['panel'], .35)
    c['selection'] = mix_color(c['panel'], c['accent'], .22)
    c['accenttext'] = '#ffffff' if QColor(c['accent']).lightness() < 128 else '#181818'
    return c


def stylesheet(c):
    chevron = (Path(__file__).resolve().parent/'icons'/('chevron-dark.svg' if QColor(c['surface']).lightness() < 128 else 'chevron-light.svg')).as_posix()
    return f'''
    QMainWindow, QWidget#root {{ background: {c['bg']}; color: {c['text']}; font-family: "Noto Sans CJK TC", "Noto Sans", sans-serif; font-size: 13px; }}
    QDialog {{ background: {c['panel']}; color: {c['text']}; }}
    QFrame#details {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 7px; }}
    QFrame#themeCard {{ background: {c['panel']}; border: 1px solid {c['border']}; border-radius: 6px; }}
    QLabel {{ color: {c['text']}; background: transparent; }}
    QLabel#muted {{ color: {c['sub']}; }}
    QLabel#title {{ font-size: 23px; font-weight: 700; }}
    QLabel#section {{ font-size: 16px; font-weight: 700; }}
    QLabel#caption {{ color: {c['sub']}; font-size: 11px; font-weight: 700; }}
    QLabel#badge {{ color: {c['text']}; background: {c['surface']}; border-radius: 4px; padding: 6px 10px; font-weight: 600; }}
    QLineEdit {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 10px 12px; selection-background-color: {c['selection']}; selection-color: {c['text']}; }}
    QLineEdit:focus {{ border: 1px solid {c['accent']}; }}
    QCheckBox {{ color: {c['text']}; background: transparent; spacing: 6px; }}
    QPlainTextEdit {{ background: {c['bg']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 8px; selection-background-color: {c['selection']}; }}
    QFrame#operation {{ background: {c['output']}; border: 1px solid {c['border']}; border-radius: 6px; }}
    QPlainTextEdit#operationOutput {{ background: {c['output']}; color: {c['text']}; border: 0; padding: 6px; selection-background-color: {c['selection']}; }}
    QProgressBar {{ background: {c['surface']}; border: 0; border-radius: 3px; min-height: 7px; max-height: 7px; }}
    QProgressBar::chunk {{ background: {c['accent']}; border-radius: 3px; }}
    QPushButton {{ color: {c['text']}; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 9px 12px; }}
    QPushButton:hover {{ border-color: {c['accent']}; }}
    QPushButton:disabled {{ color: {c['sub']}; background: {c['panel']}; border-color: {c['border']}; }}
    QToolButton#install {{ color: {c['text']}; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 9px 12px; }}
    QToolButton#install:hover {{ border-color: {c['accent']}; }}
    QToolButton#install:disabled {{ color: {c['sub']}; background: {c['panel']}; }}
    QToolButton#install {{ padding-right: 34px; }}
    QToolButton#install::menu-button {{ subcontrol-origin: padding; subcontrol-position: top right; width: 26px; border-left: 1px solid {c['border']}; }}
    QToolButton#install::menu-button:hover {{ background: {c['selection']}; border-top-right-radius: 4px; border-bottom-right-radius: 4px; }}
    QMenu {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']}; padding: 5px; }}
    QMenu::item {{ background: transparent; padding: 9px 22px 9px 12px; border-radius: 4px; }}
    QMenu::item:selected {{ background: {c['selection']}; color: {c['text']}; }}
    QComboBox {{ color: {c['text']}; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 8px 12px; min-height: 20px; }}
    QComboBox:hover, QComboBox:focus {{ border-color: {c['accent']}; }}
    QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: top right; width: 28px; border-left: 1px solid {c['border']}; }}
    QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 8px; }}
    QComboBox QAbstractItemView, QListView, QTreeView {{ color: {c['text']}; background: {c['panel']}; border: 1px solid {c['border']}; selection-background-color: {c['selection']}; selection-color: {c['text']}; outline: 0; }}
    QFileDialog QToolButton {{ color: {c['text']}; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 4px; padding: 5px; }}
    QFileDialog QToolButton:hover {{ border-color: {c['accent']}; }}
    QFileDialog QSplitter::handle {{ background: {c['bg']}; }}
    QPushButton#nav {{ background: transparent; border: 1px solid {c['border']}; padding: 7px 13px; }}
    QPushButton#nav:hover, QPushButton#nav:focus {{ border-color: {c['accent']}; }}
    QPushButton#nav:checked {{ background: {c['selection']}; color: {c['accent']}; border-color: {c['accent']}; font-weight: 700; }}
    QPushButton#help {{ background: transparent; padding: 7px 13px; font-size: 13px; }}
    QTableView {{ background: {c['panel']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 6px; gridline-color: {c['border']}; selection-background-color: {c['selection']}; selection-color: {c['text']}; outline: 0; }}
    QTableView::item {{ padding: 7px 10px; border-bottom: 1px solid {c['border']}; }}
    QHeaderView {{ background: {c['panel']}; }}
    QHeaderView::section {{ background: {c['panel']}; color: {c['sub']}; border: 0; border-right: 1px solid {c['border']}; border-bottom: 1px solid {c['border']}; padding: 10px; font-size: 11px; font-weight: 700; }}
    QScrollBar:vertical {{ background: transparent; width: 9px; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 25px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QSplitter::handle:horizontal {{ background: {c['bg']}; border: 0; }}
    QSplitter::handle:horizontal:hover {{ background: {c['selection']}; border-radius: 4px; }}
    QSplitter::handle:vertical {{ background: {c['bg']}; border: 0; }}
    QSplitter::handle:vertical:hover {{ background: {c['selection']}; border-radius: 4px; }}
    QScrollArea {{ background: transparent; border: 0; }}
    '''


class Model(QAbstractTableModel):
    headers = ('名稱 / 套件 ID', '來源', '版本', '範圍 / 狀態')
    def __init__(self):
        super().__init__(); self.rows = []
    def rowCount(self, parent=QModelIndex()): return len(self.rows) if not parent.isValid() else 0
    def columnCount(self, parent=QModelIndex()): return len(self.headers) if not parent.isValid() else 0
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        p = self.rows[index.row()]
        if role == Qt.DisplayRole: return (p.name, p.manager, p.version, p.appimage_state or p.scope)[index.column()]
        if role == Qt.DecorationRole and index.column() == 0 and p.icon:
            return QIcon(p.icon) if Path(p.icon).is_absolute() else QIcon.fromTheme(p.icon)
        if role == Qt.ToolTipRole: return p.ident
        if role == Qt.UserRole: return p
        return None
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole: return self.headers[section]
        if orientation == Qt.Horizontal and role == Qt.ToolTipRole: return '拖曳欄位邊界調整寬度，雙擊邊界自動調整'
        return None
    def replace(self, rows):
        self.beginResetModel(); self.rows = rows; self.endResetModel()


class Filter(QSortFilterProxyModel):
    def __init__(self):
        super().__init__(); self.query = ''; self.manager = '全部來源'; self.applications_only=False; self.setSortCaseSensitivity(Qt.CaseInsensitive)
    def filterAcceptsRow(self, row, parent):
        p = self.sourceModel().rows[row]
        matches = (self.manager == '全部來源' or p.manager == self.manager or
                   (self.manager == '開發工具' and p.manager in ('pipx', 'npm global', 'Cargo')))
        return matches and (not self.applications_only or p.is_application) and (not self.query or self.query in ' '.join((p.name, p.ident, p.description)).casefold())
    def set_query(self, query): self.query = query.strip().casefold(); self.invalidateFilter()
    def set_manager(self, manager): self.manager = manager; self.invalidateFilter()
    def set_applications_only(self, enabled): self.applications_only=enabled; self.invalidateFilter()


class FittedHeader(QHeaderView):
    """Keep the outside edges fixed while adjacent columns share a divider."""
    def __init__(self, table):
        super().__init__(Qt.Horizontal, table)
        self.table = table
        self.adjusting = False
        self.fit_pending = False

    def enable_fitting(self):
        self.sectionResized.connect(self.balance_sections)
        self.table.viewport().installEventFilter(self)
        self.schedule_fit()

    def balance_sections(self, index, old_size, new_size):
        if self.adjusting or index >= self.count() - 1:
            return
        neighbour = index + 1
        neighbour_size = self.sectionSize(neighbour)
        delta = new_size - old_size
        # A boundary cannot move past the next column's minimum width.
        delta = min(delta, neighbour_size - self.minimumSectionSize())
        self.adjusting = True
        try:
            if old_size + delta != new_size:
                self.resizeSection(index, old_size + delta)
            self.resizeSection(neighbour, neighbour_size - delta)
        finally:
            self.adjusting = False

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Resize:
            self.schedule_fit()
        return super().eventFilter(watched, event)

    def schedule_fit(self):
        if not self.fit_pending:
            self.fit_pending = True
            QTimer.singleShot(0, self.fit_to_viewport)

    def fit_to_viewport(self):
        self.fit_pending = False
        if self.count() < 2 or self.table.viewport().width() <= 0:
            return
        # The last column fills remaining space. Shrink other columns only as
        # needed when the window or detail panel makes the table narrower.
        available = self.table.viewport().width() - self.minimumSectionSize()
        overflow = sum(self.sectionSize(i) for i in range(self.count() - 1)) - available
        self.adjusting = True
        try:
            if overflow > 0:
                for index in (0, 2, 1):
                    shrink = min(overflow, self.sectionSize(index) - self.minimumSectionSize())
                    if shrink > 0:
                        self.resizeSection(index, self.sectionSize(index) - shrink)
                        overflow -= shrink
                    if overflow <= 0:
                        break
            used = sum(self.sectionSize(i) for i in range(self.count() - 1))
            self.resizeSection(self.count() - 1, max(self.minimumSectionSize(), self.table.viewport().width() - used))
        finally:
            self.adjusting = False


class Worker(QObject):
    done = pyqtSignal(object)
    def run(self): self.done.emit(scan_all())


class Task(QThread):
    result_ready = pyqtSignal(object, object)

    def __init__(self, fn, parent=None):
        super().__init__(parent); self.fn = fn

    def run(self):
        try:
            self.result_ready.emit(self.fn(), None)
        except Exception as exc:
            self.result_ready.emit(None, str(exc) or type(exc).__name__)


class OperationTask(QThread):
    output = pyqtSignal(str)
    progress = pyqtSignal(int)
    result_ready = pyqtSignal(object, object)

    def __init__(self, operation, parent=None):
        super().__init__(parent); self.operation = operation

    def run(self):
        try:
            if self.operation.argv:
                self.output.emit('$ ' + shlex.join(self.operation.argv))
            else:
                self.output.emit('正在複製 AppImage 並建立桌面捷徑。')
            result = actions.execute(self.operation, self.output.emit, self.progress.emit)
            self.result_ready.emit(result, None)
        except Exception as exc:
            self.result_ready.emit(None, str(exc) or type(exc).__name__)


class BatchOperationTask(QThread):
    output=pyqtSignal(str)
    progress=pyqtSignal(int)
    result_ready=pyqtSignal(int,object)
    def __init__(self,operations,parent=None):
        super().__init__(parent); self.operations=operations
    def run(self):
        failures=[]; succeeded=0; total=len(self.operations)
        for index,operation in enumerate(self.operations):
            self.output.emit(f'[{index+1}/{total}] {operation.package.name}（{operation.package.manager}）')
            self.output.emit('$ '+shlex.join(operation.argv))
            try:
                actions.execute(operation,self.output.emit,lambda value,i=index:self.progress.emit(min(99,(i*100+value)//total)))
                succeeded+=1; self.output.emit('已完成：'+operation.package.name)
            except Exception as exc:
                message=str(exc) or type(exc).__name__; failures.append((operation.package.name,message))
                self.output.emit('未完成：'+operation.package.name+' — '+message.split('\n\n',1)[0])
            self.progress.emit(min(99,((index+1)*100)//total))
        self.result_ready.emit(succeeded,failures)


class ThemeEditor(QDialog):
    """Edit a draft palette; changes are applied only after saving."""
    def __init__(self, colors, parent=None):
        super().__init__(parent); self.setWindowTitle('自訂配色'); self.setMinimumWidth(440)
        self.colors=dict(colors); self.color_buttons={}
        layout=QVBoxLayout(self); layout.setContentsMargins(22,20,22,20); layout.setSpacing(14)
        layout.addWidget(QLabel('選擇你喜歡的顏色組合'))
        grid=QGridLayout(); grid.setVerticalSpacing(10)
        for row,(key,label) in enumerate((('bg','視窗背景'),('panel','面板'),('text','文字'),('accent','重點顏色'),('output','輸出欄'))):
            grid.addWidget(QLabel(label),row,0)
            button=QPushButton(); button.setMinimumWidth(150)
            button.setObjectName('color-'+key)
            button.clicked.connect(lambda checked=False,k=key:self.pick_color(k))
            grid.addWidget(button,row,1); self.color_buttons[key]=button
        layout.addLayout(grid)
        self.preview=QLabel('配色預覽     文字與輸出內容'); self.preview.setMinimumHeight(54); self.preview.setAlignment(Qt.AlignCenter); layout.addWidget(self.preview)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('儲存並套用'); buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.update_preview()
    def pick_color(self, key):
        selected=QColorDialog.getColor(QColor(self.colors[key]), self, '選擇顏色', options=QColorDialog.DontUseNativeDialog)
        if selected.isValid(): self.colors[key]=selected.name(); self.update_preview()
    def update_preview(self):
        for key,button in self.color_buttons.items():
            color=self.colors[key]; fg='#ffffff' if QColor(color).lightness()<128 else '#181818'
            button.setText(color.upper()); button.setStyleSheet(f'QPushButton {{ background: {color}; color: {fg}; border: 1px solid #888888; border-radius: 5px; padding: 8px 12px; }}')
        c=custom_palette(self.colors)
        self.preview.setStyleSheet(f"background: {c['output']}; color: {c['text']}; border: 1px solid {c['accent']}; border-radius: 5px; padding: 8px;")


class Window(QMainWindow):
    def __init__(self, settings=None):
        super().__init__(); self.setWindowTitle('PackScope — 軟體透視'); self.resize(1350, 820); self.setMinimumSize(920, 580)
        self.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/'assets'/'packscope.svg')))
        paths=QIcon.themeSearchPaths()
        for path in (str(Path.home()/'.local/share/icons'),str(Path.home()/'.icons'),'/usr/share/icons','/usr/local/share/icons'):
            if path not in paths and Path(path).is_dir(): paths.append(path)
        QIcon.setThemeSearchPaths(paths)
        if not QIcon.themeName():
            QIcon.setThemeName('Yaru' if Path('/usr/share/icons/Yaru/index.theme').is_file() else 'Adwaita')
        self.settings = settings if settings is not None else QSettings('PackScope','PackScope')
        try: stored=json.loads(self.settings.value('theme/custom','{}',type=str))
        except (TypeError,ValueError): stored={}
        self.custom_colors=valid_custom_colors(stored)
        self.has_custom=self.custom_colors is not None
        if not self.has_custom: self.custom_colors={k:DARK[k] for k in CUSTOM_KEYS}
        self.theme_name=self.settings.value('theme/selected','dark',type=str)
        if self.theme_name not in ('dark','light','custom'): self.theme_name='dark'
        self.current_colors=DARK; self.is_dark=True
        self.results = []; self.thread = None; self.jobs = set(); self.operation_busy = False; self.manual_scan_pending = False; self.refresh_after_scan = False; self.buttons = {}
        self.launch_generation = 0; self.launch_targets = []
        self.launch_timer = QTimer(self); self.launch_timer.setSingleShot(True); self.launch_timer.timeout.connect(self.discover_launchers)
        self.build(); self.apply_theme(); self.restore_view(); self.refresh()
    def label(self, text, name=None, wrap=False):
        l=QLabel(text); l.setTextFormat(Qt.PlainText); l.setWordWrap(wrap); l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if name: l.setObjectName(name)
        return l
    def build(self):
        root=QWidget(); root.setObjectName('root'); self.setCentralWidget(root)
        main=QVBoxLayout(root); main.setContentsMargins(22,22,22,22); main.setSpacing(15)
        top=QHBoxLayout(); heading=QVBoxLayout(); heading.setSpacing(3)
        heading.addWidget(self.label('已安裝軟體','title')); heading.addWidget(self.label('PackScope  ·  軟體管理','muted')); top.addLayout(heading); top.addStretch()
        self.install_button=QToolButton(); self.install_button.setObjectName('install'); self.install_button.setText('安裝軟體'); self.install_button.setPopupMode(QToolButton.MenuButtonPopup); self.install_button.clicked.connect(self.install_software)
        install_menu=QMenu(self.install_button); install_menu.addAction('依名稱安裝',self.install_by_name); self.install_button.setMenu(install_menu); self.install_button.setToolTip('選擇安裝檔；按右側箭頭可依名稱安裝'); top.addWidget(self.install_button)
        self.update_button=QPushButton('檢查更新'); self.update_button.setToolTip('APT 和 Flatpak 使用本機快取；Snap 會連線查詢。不會安裝更新。'); self.update_button.clicked.connect(self.check_updates); top.addWidget(self.update_button)
        export_button=QPushButton('匯出清單'); export_button.clicked.connect(self.export_list); top.addWidget(export_button)
        self.theme=QPushButton('☼  切換主題'); self.theme.clicked.connect(self.toggle_theme); top.addWidget(self.theme)
        self.refresh_button=QPushButton('↻  重新掃描'); self.refresh_button.clicked.connect(self.manual_refresh); top.addWidget(self.refresh_button); main.addLayout(top)
        controls=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText('搜尋名稱、套件 ID 或描述…'); self.search.setClearButtonEnabled(True); controls.addWidget(self.search,1)
        self.app_filter=QCheckBox('僅顯示應用程式'); self.app_filter.setToolTip('預設只看辨識到的應用程式；取消勾選可查看系統套件和開發工具。辨識結果可能有遺漏。'); self.app_filter.toggled.connect(self.filter_applications); controls.addWidget(self.app_filter)
        self.count=self.label('準備掃描…','badge'); controls.addWidget(self.count); main.addLayout(controls)
        sources=QHBoxLayout(); sources.setSpacing(7); sources.addWidget(self.label('來源','caption')); sources.addSpacing(4)
        for name in ('全部來源','APT / dpkg','Snap','Flatpak','AppImage','開發工具'):
            button=QPushButton(name); button.setObjectName('nav'); button.setCheckable(True); button.clicked.connect(lambda checked, n=name:self.select_manager(n)); sources.addWidget(button); self.buttons[name]=button
        self.sources_help_button=QPushButton('?'); self.sources_help_button.setObjectName('help'); self.sources_help_button.setFixedSize(68,40); self.sources_help_button.setToolTip('了解各種軟體來源'); self.sources_help_button.setAccessibleName('了解軟體來源'); self.sources_help_button.clicked.connect(self.show_sources_help); sources.addWidget(self.sources_help_button)
        self.buttons['全部來源'].setChecked(True); sources.addStretch(); main.addLayout(sources)
        vertical_splitter=QSplitter(Qt.Vertical); self.vertical_splitter=vertical_splitter; vertical_splitter.setHandleWidth(8); vertical_splitter.setChildrenCollapsible(False); main.addWidget(vertical_splitter,1)
        splitter=QSplitter(Qt.Horizontal); self.splitter=splitter; splitter.setHandleWidth(10); splitter.setChildrenCollapsible(False); vertical_splitter.addWidget(splitter)
        self.model=Model(); self.proxy=Filter(); self.proxy.setSourceModel(self.model); self.search.textChanged.connect(self.search_changed)
        self.table=QTableView(); self.table.setMinimumWidth(350); self.table.setModel(self.proxy); self.table.setHorizontalHeader(FittedHeader(self.table)); self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.setShowGrid(False); self.table.verticalHeader().hide(); self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.setSortingEnabled(True); self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(55)
        for i, width in ((0,230),(1,115),(2,165),(3,75)):
            self.table.setColumnWidth(i,width)
        self.table.horizontalHeader().enable_fitting()
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.table.selectionModel().currentRowChanged.connect(self.show_detail); splitter.addWidget(self.table)
        details=QFrame(); details.setObjectName('details')
        dl=QVBoxLayout(details); dl.setContentsMargins(20,22,20,20); dl.setSpacing(9)
        dl.addWidget(self.label('來源透視','caption')); self.detail_name=self.label('選取一個項目','section',True); dl.addWidget(self.detail_name)
        self.detail_desc=self.label('在清單中選擇軟體，即可查看它目前的管理方式與來源證據。','muted',True); dl.addWidget(self.detail_desc); dl.addSpacing(5)
        action_row=QHBoxLayout()
        self.open_button=QPushButton('開啟'); self.open_button.setEnabled(False); self.open_button.clicked.connect(self.open_selected); action_row.addWidget(self.open_button)
        self.install_update_button=QPushButton('更新'); self.install_update_button.setEnabled(False); self.install_update_button.clicked.connect(lambda:self.apply_selected('update')); action_row.addWidget(self.install_update_button)
        self.remove_button=QPushButton('移除'); self.remove_button.setEnabled(False); self.remove_button.clicked.connect(lambda:self.apply_selected('remove')); action_row.addWidget(self.remove_button); dl.addLayout(action_row)
        self.info_button=QPushButton('查看完整資料'); self.info_button.setEnabled(False); self.info_button.clicked.connect(self.show_more); dl.addWidget(self.info_button)
        self.history_button=QPushButton('變更紀錄'); self.history_button.setEnabled(False); self.history_button.clicked.connect(self.show_history); dl.addWidget(self.history_button)
        dl.addSpacing(8)
        self.detail_fields=[]
        for title in ('目前管理器','套件 ID','版本','安裝範圍','來源證據','檔案位置'):
            dl.addWidget(self.label(title,'caption')); value=self.label('—',None,True); value.setTextFormat(Qt.PlainText); dl.addWidget(value); dl.addSpacing(5); self.detail_fields.append(value)
        dl.addStretch(); dl.addWidget(self.label('最初安裝方式：未知','badge'))
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame); scroll.setMinimumWidth(220); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setWidget(details)
        splitter.addWidget(scroll); splitter.setStretchFactor(0,4); splitter.setStretchFactor(1,2); splitter.setSizes([850,320])
        splitter.handle(1).setToolTip('拖曳此邊界調整清單與詳細資料的寬度')
        self.operation_panel=QFrame(); self.operation_panel.setObjectName('operation')
        op_layout=QVBoxLayout(self.operation_panel); op_layout.setContentsMargins(4,4,4,4); op_layout.setSpacing(2)
        self.operation_bar=QProgressBar(); self.operation_bar.setRange(0,100); self.operation_bar.setValue(0); self.operation_bar.setTextVisible(False); self.operation_bar.hide(); op_layout.addWidget(self.operation_bar)
        self.operation_output=QPlainTextEdit(); self.operation_output.setObjectName('operationOutput'); self.operation_output.setReadOnly(True); self.operation_output.setMaximumBlockCount(1500); self.operation_output.setMinimumHeight(40)
        self.operation_output.setFont(QFont('monospace',9)); op_layout.addWidget(self.operation_output)
        vertical_splitter.addWidget(self.operation_panel); vertical_splitter.setStretchFactor(0,1); vertical_splitter.setStretchFactor(1,0); vertical_splitter.setSizes([600,110])
        vertical_splitter.handle(1).setToolTip('拖曳調整輸出區高度')
        self.status=self.label('正在準備…','muted',True); main.addWidget(self.status)
    def apply_theme(self):
        self.current_colors = {'dark':DARK, 'light':LIGHT, 'custom':custom_palette(self.custom_colors)}[self.theme_name]
        self.is_dark=QColor(self.current_colors['panel']).lightness()<128
        self.setStyleSheet(stylesheet(self.current_colors))
    def set_theme(self, name, persist=True):
        if name not in ('dark','light','custom'): raise ValueError('未知主題。')
        self.theme_name=name; self.apply_theme()
        if persist: self.settings.setValue('theme/selected',name); self.settings.sync()
    def edit_custom_theme(self):
        initial=self.custom_colors if self.has_custom else {k:self.current_colors[k] for k in CUSTOM_KEYS}
        editor=ThemeEditor(initial,self)
        if editor.exec_() != QDialog.Accepted: return False
        colors=valid_custom_colors(editor.colors)
        if colors is None: return False
        self.custom_colors=colors; self.has_custom=True
        self.settings.setValue('theme/custom',json.dumps(colors,ensure_ascii=False))
        self.set_theme('custom'); return True
    def toggle_theme(self):
        dialog=QDialog(self); dialog.setWindowTitle('選擇主題'); dialog.setMinimumWidth(580)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(22,20,22,20); layout.setSpacing(16)
        layout.addWidget(self.label('選擇主題','section'))
        cards=QHBoxLayout(); cards.setSpacing(10); layout.addLayout(cards)
        for key,title,colors in (('dark','深色',DARK),('light','淺色',LIGHT),('custom','自訂',custom_palette(self.custom_colors))):
            card=QFrame(); card.setObjectName('themeCard'); card_layout=QVBoxLayout(card); card_layout.setSpacing(8)
            card_layout.addWidget(self.label(title,'caption'))
            swatches=QHBoxLayout(); swatches.setSpacing(4)
            for color in (colors['bg'],colors['panel'],colors['accent'],colors['output']):
                swatch=QLabel(); swatch.setFixedSize(26,26); swatch.setStyleSheet(f'background: {color}; border: 1px solid {colors["border"]}; border-radius: 4px;'); swatches.addWidget(swatch)
            swatches.addStretch(); card_layout.addLayout(swatches)
            button=QPushButton('使用中' if self.theme_name==key else '套用'); button.setEnabled(self.theme_name!=key)
            button.setObjectName('theme-'+key)
            def choose(checked=False,theme=key): self.set_theme(theme); dialog.accept()
            button.clicked.connect(choose); card_layout.addWidget(button); cards.addWidget(card)
        controls=QHBoxLayout(); customize=QPushButton('自訂配色…'); customize.setObjectName('theme-customize'); controls.addWidget(customize); controls.addStretch()
        close=QPushButton('關閉'); close.clicked.connect(dialog.reject); controls.addWidget(close); layout.addLayout(controls)
        def customize_theme():
            if self.edit_custom_theme(): dialog.accept()
        customize.clicked.connect(customize_theme); dialog.exec_()
    def restore_view(self):
        self.app_filter.setChecked(self.settings.value('view/applications_only', True, type=bool))
        source=self.settings.value('view/source', '全部來源', type=str)
        self.select_manager(source if source in self.buttons else '全部來源')
        self.search.setText(self.settings.value('view/query', '', type=str))
        for key, widget in (('view/columns', self.table.horizontalHeader()),
                            ('view/panels', self.splitter),
                            ('view/output', self.vertical_splitter)):
            state=self.settings.value(key)
            if state is not None: widget.restoreState(state)
    def select_manager(self, name):
        if name == '開發工具' and self.app_filter.isChecked():
            self.app_filter.setChecked(False)
        for key, button in self.buttons.items(): button.setChecked(key==name)
        self.proxy.set_manager(name); self.settings.setValue('view/source', name)
        self.clear_details(); self.update_count()
    def search_changed(self, text):
        self.proxy.set_query(text); self.settings.setValue('view/query', text)
        self.clear_details(); self.update_count()
    def filter_applications(self, enabled):
        self.proxy.set_applications_only(enabled); self.settings.setValue('view/applications_only', enabled)
        self.clear_details(); self.update_count()
    def clear_details(self):
        self.table.clearSelection(); self.table.setCurrentIndex(QModelIndex()); self.show_detail(QModelIndex(), QModelIndex())
    def update_count(self):
        visible=self.proxy.rowCount()
        self.count.setText(f'顯示 {visible:,} / 全部 {len(self.model.rows):,} 項')
        matching=(p for p in self.model.rows
                  if (not self.proxy.applications_only or p.is_application)
                  and (not self.proxy.query or self.proxy.query in ' '.join((p.name,p.ident,p.description)).casefold()))
        counts={key:0 for key in self.buttons}
        for package in matching:
            counts['全部來源']+=1
            if package.manager in counts: counts[package.manager]+=1
            elif package.manager in ('pipx','npm global','Cargo'): counts['開發工具']+=1
        labels={'全部來源':'全部','APT / dpkg':'APT','Snap':'Snap','Flatpak':'Flatpak',
                'AppImage':'AppImage','開發工具':'開發工具'}
        for key,button in self.buttons.items():
            button.setText(f'{labels[key]} · {counts[key]:,}')

    def log_event(self, message):
        self.operation_output.appendPlainText(f'[{datetime.now().strftime("%H:%M:%S")}] {message}')
    def manual_refresh(self):
        if self.operation_busy or self.thread is not None: return
        self.manual_scan_pending=True; self.log_event('開始重新掃描軟體清單。'); self.refresh()
    def refresh(self):
        if self.operation_busy or self.thread is not None: return
        self.refresh_button.setEnabled(False); self.status.setText('正在背景掃描本機資料，請稍候…')
        self.thread=QThread(self); self.worker=Worker(); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.done.connect(self.scan_done); self.worker.done.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater); self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.scan_finished); self.thread.start()
    def scan_finished(self):
        self.thread=None; self.refresh_button.setEnabled(not self.operation_busy)
        if self.refresh_after_scan and not self.operation_busy:
            self.refresh_after_scan=False; self.refresh()
    def scan_done(self, results):
        self.results=results; rows=sorted((p for r in results for p in r.packages), key=lambda p:p.name.casefold())
        self.model.replace(rows); self.update_count(); self.show_detail(QModelIndex(),QModelIndex())
        parts=[]
        for result in results:
            state=f'{len(result.packages):,}' if result.status=='ok' else ('未安裝' if result.status=='unavailable' else '讀取失敗')
            parts.append(f'{result.manager} {state}')
        self.status.setText('  ·  '.join(parts) + '    |    '+datetime.now().strftime('%H:%M')+' 掃描完成')
        if self.manual_scan_pending:
            self.log_event('重新掃描完成：' + '；'.join(parts)); self.manual_scan_pending=False
        self.status.setToolTip('\n'.join(f'{r.manager}：{r.detail or "讀取成功"}' for r in results))
        developer_info=[]
        for r in results:
            if r.manager in self.buttons: self.buttons[r.manager].setToolTip(r.detail or '讀取成功')
            elif r.manager in ('pipx', 'npm global', 'Cargo'): developer_info.append(f'{r.manager}：{r.detail or "讀取成功"}')
        self.buttons['開發工具'].setToolTip('\n'.join(developer_info))
    def show_detail(self, current, previous):
        self.launch_generation += 1; self.launch_timer.stop(); self.launch_targets = []
        self.open_button.setEnabled(False); self.open_button.setText('開啟')
        if not current.isValid():
            self.detail_name.setText('選取一個項目'); self.detail_desc.setText('在清單中選擇軟體，即可查看它目前的管理方式與來源證據。')
            self.open_button.setToolTip('請先選擇軟體。')
            self.info_button.setEnabled(False); self.history_button.setEnabled(False); self.install_update_button.setEnabled(False); self.remove_button.setEnabled(False)
            for field in self.detail_fields: field.setText('—')
            return
        p=self.proxy.data(self.proxy.index(current.row(),0),Qt.UserRole)
        if p is None: return
        self.detail_name.setText(p.name); self.detail_desc.setText(p.description or '沒有可用的描述')
        self.info_button.setEnabled(True); self.history_button.setEnabled(p.manager == 'APT / dpkg')
        self.install_update_button.setEnabled(not self.operation_busy and p.manager in ('APT / dpkg','Snap','Flatpak','pipx','npm global','Cargo'))
        self.remove_button.setEnabled(not self.operation_busy and p.manager in ('APT / dpkg','Snap','Flatpak','pipx','npm global','Cargo','AppImage'))
        for field, value in zip(self.detail_fields,(p.manager,p.ident,p.version,p.scope,p.evidence,p.location or '未知')): field.setText(value)
        self.open_button.setToolTip('正在查詢可用的啟動方式…'); self.launch_timer.start(180)
    def selected_package(self):
        current=self.table.currentIndex()
        return self.proxy.data(self.proxy.index(current.row(),0),Qt.UserRole) if current.isValid() else None
    def run_task(self, fn, callback):
        task=Task(fn,self); self.jobs.add(task)
        task.result_ready.connect(callback)
        task.finished.connect(lambda: self.jobs.discard(task))
        task.finished.connect(task.deleteLater); task.start()
    def operation_progress(self, value):
        self.operation_bar.setRange(0,100); self.operation_bar.setValue(value)
    def discover_launchers(self):
        package=self.selected_package(); generation=self.launch_generation
        if not package: return
        def done(targets,error):
            if generation != self.launch_generation or package != self.selected_package(): return
            self.launch_targets=targets or []
            if error: self.open_button.setToolTip('無法確認啟動方式：'+error)
            elif not self.launch_targets: self.open_button.setToolTip('找不到可直接開啟的桌面程式。')
            else: self.open_button.setToolTip('開啟所選的程式。')
            self.open_button.setEnabled(bool(self.launch_targets) and not self.operation_busy)
        self.run_task(lambda:launch.find_targets(package),done)
    def open_selected(self):
        if not self.launch_targets or self.operation_busy: return
        target=self.launch_targets[0]
        if len(self.launch_targets)>1:
            labels=[f'{item.label}  —  {item.path or item.argv[0]}' for item in self.launch_targets]
            selected,ok=QInputDialog.getItem(self,'選擇要開啟的程式','此套件包含多個程式：',labels,0,False)
            if not ok: return
            target=self.launch_targets[labels.index(selected)]
        self.status.setText(f'正在開啟 {target.label}…')
        self.log_event(f'正在開啟：{target.label}')
        def done(result,error):
            if error:
                self.log_event(f'開啟失敗：{target.label} — {error}')
                self.status.setText('無法開啟程式。'); QMessageBox.warning(self,'無法開啟程式',error)
            else:
                self.log_event(f'{target.label}：{result}'); self.status.setText(f'{target.label}：{result}')
        self.run_task(lambda:launch.start_target(target),done)
    def show_sources_help(self):
        QMessageBox.information(self,'軟體來源說明',
            'APT / dpkg（.deb）\n.deb 是 Ubuntu／Debian 的套件格式；dpkg 記錄與管理套件，APT 可從軟體來源取得套件並處理相依套件。\n\n'
            'Snap\n由 snapd 管理的套件，通常從 Snap Store 取得，可包含桌面程式或背景服務。\n\n'
            'Flatpak\n可分為使用者和系統範圍，通常從 Flathub 等來源取得；清單也可能包含執行環境。\n\n'
            'AppImage\n通常是可直接執行的獨立檔案；清單只涵蓋目前設定的掃描位置。\n\n'
            'pipx\n在獨立 Python 虛擬環境中管理應用程式。\n\n'
            'npm global\n目前 Node.js 環境中的全域套件與工具。\n\n'
            'Cargo\n由 Cargo 安裝到目前 Cargo 環境的 Rust 工具。\n\n'
            '清單顯示的是目前的管理方式，不一定能確定最初如何安裝。')
    def text_dialog(self, title, content):
        dialog=QDialog(self); dialog.setWindowTitle(title); dialog.resize(760,580)
        layout=QVBoxLayout(dialog); text=QPlainTextEdit(); text.setReadOnly(True); text.setPlainText(content); layout.addWidget(text)
        buttons=QDialogButtonBox(QDialogButtonBox.Close); buttons.button(QDialogButtonBox.Close).setText('關閉'); buttons.rejected.connect(dialog.reject); layout.addWidget(buttons); dialog.exec_()
    def show_more(self):
        package=self.selected_package()
        if not package: return
        self.status.setText(f'正在讀取 {package.name} 的詳細資料…')
        self.log_event(f'讀取詳細資料：{package.name}')
        def done(result,error):
            self.status.setText('詳細資料讀取完成。' if not error else '詳細資料讀取失敗。')
            self.log_event(f'{package.name} 的詳細資料' + (f'讀取失敗：{error}' if error else '已讀取。'))
            if error: QMessageBox.warning(self,'無法讀取詳細資料',error)
            else: self.text_dialog(f'{package.name} — 完整資料','\n'.join(line.lstrip() for line in result.splitlines()))
        self.run_task(lambda:backend.details(package),done)
    def install_software(self):
        if self.operation_busy: return
        path,_=QFileDialog.getOpenFileName(self,'選擇安裝檔','','支援的安裝檔 (*.deb *.DEB *.snap *.SNAP *.flatpak *.FLATPAK *.flatpakref *.FLATPAKREF *.AppImage *.appimage *.APPIMAGE);;所有檔案 (*)',options=QFileDialog.DontUseNativeDialog)
        if not path: return
        try:
            operation=actions.make_file_install(path)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self,'無法安裝',str(error)); return
        self.perform_operation(operation.package,'install',operation=operation)
    def choose_install_source(self):
        dialog=QInputDialog(self); dialog.setWindowTitle('安裝軟體'); dialog.setLabelText('選擇套件來源：')
        dialog.setComboBoxItems(('APT / dpkg','Snap','Flatpak','AppImage','pipx','npm global','Cargo'))
        dialog.setComboBoxEditable(False); dialog.setMinimumWidth(360)
        dialog.setOkButtonText('繼續'); dialog.setCancelButtonText('取消')
        combo=dialog.findChild(QComboBox)
        colors=self.current_colors
        combo.view().window().setStyleSheet(
            f"QFrame {{ background: {colors['panel']}; border: 1px solid {colors['border']}; }} "
            f"QListView {{ color: {colors['text']}; background: {colors['panel']}; border: none; "
            f"selection-background-color: {colors['selection']}; selection-color: {colors['text']}; outline: none; }}")
        accepted=dialog.exec_() == QDialog.Accepted
        return dialog.textValue(),accepted
    def install_by_name(self):
        if self.operation_busy: return
        source,ok=self.choose_install_source()
        if not ok: return
        if source == 'AppImage':
            path,_=QFileDialog.getOpenFileName(self,'選擇 AppImage 檔案','','AppImage (*.AppImage *.appimage)',options=QFileDialog.DontUseNativeDialog)
            if path:
                from pathlib import Path
                self.perform_operation(Package(Path(path).stem,path,'未知','AppImage','使用者',location=path),'install')
            return
        name,ok=QInputDialog.getText(self,'安裝軟體',f'輸入 {source} 軟體名稱或套件 ID：')
        if not ok or not name.strip(): return
        if source == 'APT / dpkg':
            self.status.setText(f'正在搜尋 {name.strip()}…')
            self.log_event(f'搜尋 APT 套件：{name.strip()}')
            def found(results,error):
                if error:
                    self.log_event(f'APT 搜尋失敗：{error}')
                    self.status.setText('搜尋失敗。'); QMessageBox.warning(self,'搜尋失敗',error); return
                if not results:
                    self.log_event('APT 搜尋沒有符合的套件。')
                    self.status.setText('找不到符合的 APT 套件。'); QMessageBox.information(self,'搜尋結果','沒有找到符合的套件。'); return
                self.log_event(f'APT 搜尋完成：找到 {len(results)} 個結果。')
                labels=[f'{ident}  —  {description}' for ident,description in results]
                selected,ok=QInputDialog.getItem(self,'搜尋結果','選擇要安裝的套件：',labels,0,False)
                if not ok: self.status.setText('已取消安裝。'); return
                ident=results[labels.index(selected)][0]
                self.perform_operation(Package(ident,ident,'未知','APT / dpkg','系統'),'install')
            self.run_task(lambda:actions.search_apt(name),found); return
        scope='使用者' if source in ('pipx','npm global','Cargo') else '系統'
        remote='flathub'
        if source == 'Flatpak':
            scope,ok=QInputDialog.getItem(self,'Flatpak 安裝範圍','安裝範圍：',('使用者','系統'),0,False)
            if not ok: return
            remote,ok=QInputDialog.getText(self,'Flatpak 來源','輸入 Flatpak 遠端來源名稱：',text='flathub')
            if not ok or not remote.strip(): return
        package=Package(name.strip(),name.strip(),'未知',source,scope)
        self.perform_operation(package,'install',remote.strip())
    def apply_selected(self, action):
        package=self.selected_package()
        if package and not self.operation_busy: self.perform_operation(package,action)
    def perform_operation(self, package, action, remote='flathub', operation=None):
        try:
            operation=operation or actions.make_operation(package,action,remote)
        except ValueError as error:
            QMessageBox.warning(self,'無法執行',str(error)); return
        label={'install':'安裝','update':'更新','remove':'移除'}[action]
        detail=f'{label}「{package.name}」？\n\n來源：{package.manager}\n識別碼：{package.ident}'
        if package.manager == 'AppImage' and action == 'remove': detail+='\n\n檔案會移至垃圾桶。'
        if package.manager == 'Cargo' and action == 'update': detail+='\n\nCargo 將從目前設定的登錄來源重新安裝此工具。'
        if action == 'install' and package.location and package.manager == 'Snap': detail+='\n\n本機 Snap 檔案以 --dangerous 安裝，不會驗證商店簽章。'
        if operation.needs_auth: detail+='\n\n系統需要權限時，請在 Ubuntu 授權視窗輸入密碼。'
        if QMessageBox.question(self,label,detail,QMessageBox.Yes|QMessageBox.No,QMessageBox.No) != QMessageBox.Yes: return
        self.operation_busy=True; self.install_button.setEnabled(False); self.open_button.setEnabled(False); self.remove_button.setEnabled(False); self.install_update_button.setEnabled(False); self.refresh_button.setEnabled(False)
        self.status.setText(f'正在{label} {package.name}，請留意系統授權視窗…')
        self.operation_bar.setRange(0,0); self.operation_bar.show()
        self.log_event(f'開始{label}：{package.name}（{package.manager}）')
        if operation.needs_auth: self.operation_output.appendPlainText('如系統要求密碼，請在 Ubuntu 授權視窗中輸入。')
        def done(result,error):
            self.operation_busy=False; self.install_button.setEnabled(True)
            self.refresh_button.setEnabled(True); self.show_detail(self.table.currentIndex(),QModelIndex())
            self.status.setText(f'{label}未完成。' if error else f'{label}完成，正在重新整理清單。')
            if error:
                if self.operation_bar.maximum() == 0: self.operation_bar.setRange(0,100); self.operation_bar.setValue(0)
                self.log_event(f'{label}未完成：' + error.split('\n\n',1)[0])
            else:
                self.operation_bar.setRange(0,100); self.operation_bar.setValue(100)
                self.log_event(f'{label}完成：{package.name}')
                if action == 'install' and package.location:
                    self.search.clear(); self.select_manager(package.manager)
            if self.thread is not None: self.refresh_after_scan=True
            else: self.refresh_after_scan=False; self.refresh()
        task=OperationTask(operation,self); self.jobs.add(task)
        task.output.connect(self.operation_output.appendPlainText); task.progress.connect(self.operation_progress)
        task.result_ready.connect(done); task.finished.connect(lambda:self.jobs.discard(task)); task.finished.connect(task.deleteLater); task.start()
    def show_history(self):
        package=self.selected_package()
        if not package or package.manager != 'APT / dpkg': return
        self.status.setText(f'正在讀取 {package.name} 的變更紀錄…')
        self.log_event(f'讀取變更紀錄：{package.name}')
        def done(result,error):
            self.status.setText('變更紀錄讀取完成。' if not error else '變更紀錄讀取失敗。')
            self.log_event(f'{package.name} 的變更紀錄' + (f'讀取失敗：{error}' if error else '已讀取。'))
            if error: QMessageBox.warning(self,'無法讀取變更紀錄',error)
            else: self.text_dialog(f'{package.name} — 變更紀錄',result)
        self.run_task(lambda:backend.package_history(package),done)
    def check_updates(self):
        if self.operation_busy: return
        self.update_button.setEnabled(False); self.status.setText('正在查詢更新；Snap 可能需要連線，請稍候…')
        self.log_event('開始查詢更新。')
        def done(result,error):
            self.update_button.setEnabled(True)
            if error:
                self.log_event(f'更新查詢失敗：{error}')
                self.status.setText('更新查詢失敗。'); QMessageBox.warning(self,'無法查詢更新',error); return
            self.status.setText('更新查詢完成；未安裝或修改軟體。')
            summary=[]
            for name,note,entries,problem in result:
                state='查詢失敗' if problem else ('尚未檢查' if '尚未檢查' in note else f'{len(entries)} 項')
                summary.append(f'{name} {state}')
            self.log_event('更新查詢完成：' + '；'.join(summary))
            self.show_updates(result)
        self.run_task(backend.check_updates,done)
    def show_updates(self, sections):
        items=backend.update_items(sections,self.model.rows)
        dialog=QDialog(self); dialog.setWindowTitle('可用更新'); dialog.resize(850,520)
        layout=QVBoxLayout(dialog); layout.setContentsMargins(20,20,20,20)
        layout.addWidget(self.label('選擇要更新的項目','section'))
        table=QTableWidget(len(items),5); table.setHorizontalHeaderLabels(('選取','名稱','來源 / 範圍','目前版本','可更新版本'))
        table.setEditTriggers(QAbstractItemView.NoEditTriggers); table.setSelectionBehavior(QAbstractItemView.SelectRows); table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); table.horizontalHeader().setSectionResizeMode(1,QHeaderView.Stretch)
        for row,item in enumerate(items):
            check=QTableWidgetItem(); check.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable if item.package else Qt.NoItemFlags)
            check.setCheckState(Qt.Unchecked); check.setData(Qt.UserRole,row); table.setItem(row,0,check)
            source=item.manager+((' · '+item.package.scope) if item.package and item.manager=='Flatpak' else '')
            for col,value in enumerate((item.name,source,item.current,item.candidate),1): table.setItem(row,col,QTableWidgetItem(value))
            if not item.package:
                for col in range(5): table.item(row,col).setToolTip('目前清單找不到對應項目，請重新掃描。')
        layout.addWidget(table,1)
        notes=[]
        for name,note,entries,error in sections:
            if error: notes.append(f'{name}：查詢失敗（{error.splitlines()[0]}）')
            elif '尚未檢查' in note: notes.append(f'{name}：尚未檢查')
            elif name=='APT / dpkg' or name.startswith('Flatpak'): notes.append(f'{name}：使用本機資料')
        layout.addWidget(self.label('  ·  '.join(notes),'muted',True))
        row=QHBoxLayout(); all_button=QPushButton('全選'); row.addWidget(all_button)
        refresh=QPushButton('重新取得套件資訊'); row.addWidget(refresh); row.addStretch()
        update=QPushButton('更新選取項目'); row.addWidget(update); close=QPushButton('關閉'); close.clicked.connect(dialog.reject); row.addWidget(close); layout.addLayout(row)
        all_button.clicked.connect(lambda: [table.item(i,0).setCheckState(Qt.Checked) for i,item in enumerate(items) if item.package])
        def refresh_metadata():
            dialog.accept(); self.refresh_metadata()
        refresh.clicked.connect(refresh_metadata)
        def update_selected():
            if self.operation_busy: QMessageBox.information(dialog,'更新軟體','目前有其他作業進行中，請稍候。'); return
            chosen=[item.package for i,item in enumerate(items) if item.package and table.item(i,0).checkState()==Qt.Checked]
            if not chosen: QMessageBox.information(dialog,'更新軟體','請先選擇要更新的項目。'); return
            installed={(p.manager,p.ident,p.scope) for p in self.model.rows}
            if any((p.manager,p.ident,p.scope) not in installed for p in chosen):
                QMessageBox.warning(dialog,'清單已變更','部分項目已不在目前清單中，請重新檢查更新。'); return
            try: operations=[actions.make_operation(p,'update') for p in chosen]
            except ValueError as error: QMessageBox.warning(dialog,'無法更新',str(error)); return
            detail='\n'.join(f'{p.name}（{p.manager}）' for p in chosen)
            if QMessageBox.question(dialog,'更新軟體',f'確定更新以下 {len(chosen)} 個項目？\n\n{detail}',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
            dialog.accept(); self.run_batch(operations,'更新軟體')
        update.clicked.connect(update_selected); dialog.exec_()
    def refresh_metadata(self):
        if self.operation_busy: QMessageBox.information(self,'重新取得套件資訊','目前有其他作業進行中，請稍候。'); return
        try: operations=actions.metadata_operations()
        except ValueError as error: QMessageBox.warning(self,'無法取得資訊',str(error)); return
        if QMessageBox.question(self,'重新取得套件資訊','將連線更新 APT 與可用的 Flatpak 來源資訊，可能需要系統授權。完成後會重新檢查更新。',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        self.run_batch(operations,'重新取得套件資訊',check_after=True)
    def run_batch(self, operations, label, check_after=False):
        if self.operation_busy or not operations: return
        self.operation_busy=True; self.install_button.setEnabled(False); self.update_button.setEnabled(False); self.refresh_button.setEnabled(False)
        self.open_button.setEnabled(False); self.remove_button.setEnabled(False); self.install_update_button.setEnabled(False)
        self.status.setText(f'正在{label}…'); self.operation_bar.setRange(0,0); self.operation_bar.show(); self.log_event(f'開始{label}。')
        def done(succeeded, failures):
            self.operation_busy=False; self.install_button.setEnabled(True); self.update_button.setEnabled(True); self.refresh_button.setEnabled(True)
            self.show_detail(self.table.currentIndex(),QModelIndex()); self.operation_bar.setRange(0,100); self.operation_bar.setValue(100 if not failures else 0)
            result=f'{label}完成：成功 {succeeded} 項，失敗 {len(failures)} 項。'
            self.status.setText(result); self.log_event(result)
            if failures: QMessageBox.warning(self,f'{label}未完全完成',result+'\n\n'+'\n'.join(f'{name}：{error.splitlines()[0]}' for name,error in failures))
            if self.thread is not None: self.refresh_after_scan=True
            else: self.refresh_after_scan=False; self.refresh()
            if check_after: self.check_updates()
        task=BatchOperationTask(operations,self); self.jobs.add(task); task.output.connect(self.operation_output.appendPlainText); task.progress.connect(self.operation_progress)
        task.result_ready.connect(done); task.finished.connect(lambda:self.jobs.discard(task)); task.finished.connect(task.deleteLater); task.start()
    def export_list(self):
        path,chosen=QFileDialog.getSaveFileName(self,'匯出目前顯示的清單','packscope.json','JSON (*.json);;CSV (*.csv);;Markdown (*.md)')
        if not path: return
        fmt='csv' if chosen.startswith('CSV') else ('md' if chosen.startswith('Markdown') else 'json')
        if not path.lower().endswith('.'+fmt): path+='.'+fmt
        packages=[self.proxy.index(row,0).data(Qt.UserRole) for row in range(self.proxy.rowCount())]
        try:
            backend.export_inventory(path,packages,fmt)
        except (OSError,ValueError) as error:
            self.log_event(f'匯出失敗：{error}')
            QMessageBox.warning(self,'匯出失敗',str(error)); return
        self.log_event(f'已匯出 {len(packages):,} 個項目至 {path}')
        self.status.setText(f'已匯出 {len(packages):,} 個目前顯示的項目。')
    def closeEvent(self, event):
        if (self.thread and self.thread.isRunning()) or any(t.isRunning() for t in self.jobs):
            self.status.setText('正在完成目前的查詢，請稍候再關閉。'); event.ignore()
        else:
            self.settings.setValue('view/columns', self.table.horizontalHeader().saveState())
            self.settings.setValue('view/panels', self.splitter.saveState())
            self.settings.setValue('view/output', self.vertical_splitter.saveState())
            self.settings.sync()
            event.accept()


def main():
    app=QApplication(sys.argv); app.setApplicationName('PackScope'); app.setFont(QFont('Noto Sans CJK TC', 10))
    app.setDesktopFileName('packscope'); app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/'assets'/'packscope.svg')))
    translator=QTranslator(app)
    if translator.load('qtbase_zh_TW',QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)
    window=Window(); window.show(); sys.exit(app.exec_())

if __name__ == '__main__': main()
