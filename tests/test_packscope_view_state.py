import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

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
                self.assertTrue(window.app_filter.isChecked())
                self.assertEqual(window.proxy.rowCount(), 2)
                self.assertEqual(window.count.text(), '顯示 2 / 全部 4 項')
                self.assertEqual(window.buttons['APT / dpkg'].text(), 'APT · 1')
                self.assertEqual(window.buttons['開發工具'].text(), '開發工具 · 0')
                window.buttons['開發工具'].click()
                self.assertFalse(window.app_filter.isChecked())
                self.assertEqual(window.proxy.rowCount(), 1)
                self.assertEqual(window.buttons['開發工具'].text(), '開發工具 · 1')
            finally:
                self.wait_scan(window)
                window.close()

    def test_filters_and_layout_survive_restart(self):
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all', return_value=[]):
            config = str(Path(tmp) / 'settings.ini')
            window = Window(QSettings(config, QSettings.IniFormat))
            window.show()
            self.wait_scan(window)
            window.app_filter.setChecked(False)
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
                self.assertFalse(restored.app_filter.isChecked())
                self.assertEqual(restored.proxy.manager, 'Snap')
                self.assertEqual(restored.search.text(), 'browser')
                self.assertEqual(restored.table.columnWidth(0), first_width)
                self.assertEqual(restored.splitter.sizes(), first_panels)
                self.assertEqual(restored.vertical_splitter.sizes(), first_output)
            finally:
                self.wait_scan(restored)
                restored.close()


if __name__ == '__main__':
    unittest.main()
