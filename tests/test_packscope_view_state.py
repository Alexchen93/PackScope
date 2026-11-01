import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtWidgets import QApplication, QDialogButtonBox, QPlainTextEdit

from packscope.app import Window
from packscope.inventory import Package, ScanResult


class ViewStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def wait_scan(self, window):
        deadline = time.monotonic() + 4
        while window.thread is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(.01)
        self.assertIsNone(window.thread)

    def test_application_first_counts_and_developer_entry(self):
        app = Package('Editor', 'editor', '1', 'APT / dpkg', is_application=True)
        library = Package('Library', 'library', '1', 'APT / dpkg')
        snap = Package('Browser', 'browser', '1', 'Snap', is_application=True)
        tool = Package('CLI Tool', 'cli-tool', '1', 'pipx')
        results = [ScanResult('APT / dpkg', [app, library], 'ok'),
                   ScanResult('Snap', [snap], 'ok'),
                   ScanResult('pipx', [tool], 'ok')]
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all', return_value=results):
            settings = QSettings(str(Path(tmp) / 'settings.ini'), QSettings.IniFormat)
            window = Window(settings)
            window.show()
            try:
                self.wait_scan(window)
                self.assertTrue(window.app_filter.currentData())
                self.assertEqual(window.proxy.rowCount(), 2)
                self.assertEqual(window.count.text(), '顯示 2 / 全部 4 項')
                self.assertEqual(window.source_combo.itemText(window.source_combo.findData('APT / dpkg')), 'APT · 1')
                self.assertEqual(window.source_combo.itemText(window.source_combo.findData('開發工具')), '開發工具 · 0')
                window.source_combo.set_selected({'開發工具'})
                self.assertFalse(window.app_filter.currentData())
                self.assertEqual(window.proxy.rowCount(), 1)
                self.assertEqual(window.source_combo.itemText(window.source_combo.findData('開發工具')), '開發工具 · 1')
            finally:
                self.wait_scan(window)
                window.close()

    def test_multiple_sources_and_theme(self):
        rows=[Package('APT','apt','1','APT / dpkg',is_application=True),
              Package('Snap','snap','1','Snap',is_application=True),
              Package('Flat','flat','1','Flatpak',is_application=True)]
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all',return_value=[ScanResult('test',rows,'ok')]):
            settings=QSettings(str(Path(tmp)/'settings.ini'),QSettings.IniFormat)
            window=Window(settings); window.show()
            try:
                self.wait_scan(window)
                window.source_combo.set_selected({'APT / dpkg','Snap'})
                self.assertEqual(window.proxy.rowCount(),2)
                self.assertEqual(window.source_combo.selected(),{'APT / dpkg','Snap'})
                window.set_theme('light',persist=False)
                self.assertIn(window.current_colors['panel'],window.source_combo.view().window().styleSheet())
                window.source_combo.set_selected(set())
                self.assertEqual(window.proxy.rowCount(),3)
            finally:
                self.wait_scan(window); window.close()

    def test_filters_and_layout_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all', return_value=[]):
            config = str(Path(tmp) / 'settings.ini')
            window = Window(QSettings(config, QSettings.IniFormat))
            window.show()
            self.wait_scan(window)
            window.app_filter.setCurrentIndex(1)
            window.select_manager('Snap')
            window.search.setText('browser')
            window.table.setColumnWidth(0, 260)
            window.splitter.setSizes([700, 300])
            window.vertical_splitter.setSizes([500, 200])
            self.app.processEvents()
            first_width = window.table.columnWidth(0)
            first_panels = window.splitter.sizes()
            first_output = window.vertical_splitter.sizes()
            window.close()
            self.app.processEvents()

            restored = Window(QSettings(config, QSettings.IniFormat))
            restored.show()
            try:
                self.wait_scan(restored)
                self.app.processEvents()
                self.assertFalse(restored.app_filter.currentData())
                self.assertEqual(restored.proxy.manager, 'Snap')
                self.assertEqual(restored.search.text(), 'browser')
                self.assertEqual(restored.table.columnWidth(0), first_width)
                self.assertEqual(restored.splitter.sizes(), first_panels)
                self.assertEqual(restored.vertical_splitter.sizes(), first_output)
            finally:
                self.wait_scan(restored)
                restored.close()

    def test_search_debounce_keeps_only_latest_query(self):
        records=[Package('Editor','editor','1','APT / dpkg',is_application=True),
                 Package('Browser','browser','1','Snap',is_application=True)]
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all', return_value=[ScanResult('test',records,'ok')]):
            window=Window(QSettings(str(Path(tmp)/'settings.ini'),QSettings.IniFormat)); window.show()
            try:
                self.wait_scan(window)
                window.search.setText('edit'); window.search.setText('browser')
                self.assertFalse(window.table.isEnabled())
                deadline=time.monotonic()+3
                while window.search_timer.isActive() and time.monotonic()<deadline:
                    self.app.processEvents(); time.sleep(.01)
                self.assertEqual(window.proxy.query,'browser')
                self.assertEqual(window.proxy.rowCount(),1)
                self.assertTrue(window.table.isEnabled())
                self.assertEqual(window.source_combo.itemText(window.source_combo.findData('Snap')),'Snap · 1')
            finally:
                self.wait_scan(window); window.close()

    def test_scan_error_dialog_reports_reason_and_retries(self):
        calls=[]
        def scan():
            calls.append(1)
            return [ScanResult('Snap', [], 'error', '讀取失敗：permission denied')] if len(calls)==1 else [ScanResult('Snap', [], 'ok')]
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all', side_effect=scan):
            window=Window(QSettings(str(Path(tmp)/'settings.ini'),QSettings.IniFormat)); window.show()
            try:
                self.wait_scan(window)
                self.assertTrue(window.scan_issues_button.isVisible())
                def retry():
                    dialog=self.app.activeModalWidget()
                    self.assertIn('permission denied',dialog.findChild(QPlainTextEdit).toPlainText())
                    buttons=dialog.findChild(QDialogButtonBox)
                    next(button for button in buttons.buttons() if button.text()=='重新掃描').click()
                QTimer.singleShot(0,retry); window.show_scan_issues()
                self.wait_scan(window)
                self.assertEqual(len(calls),2)
                self.assertFalse(window.scan_issues_button.isVisible())
            finally:
                self.wait_scan(window); window.close()


if __name__ == '__main__':
    unittest.main()
