import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QColorDialog, QPushButton
from packscope.app import Window


class ThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def wait_scan(self, window):
        deadline=time.monotonic()+4
        while window.thread is not None and time.monotonic()<deadline:
            self.app.processEvents(); time.sleep(.01)
        self.assertIsNone(window.thread)

    def test_light_output_and_restores_custom_palette_and_selection(self):
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all',return_value=[]):
            config=str(Path(tmp)/'settings.ini')
            settings=QSettings(config,QSettings.IniFormat)
            w=Window(settings); w.show()
            try:
                self.wait_scan(w)
                w.set_theme('light')
                self.assertEqual(w.operation_output.palette().base().color().name(),'#fffdfa')
                self.assertEqual(w.operation_output.palette().text().color().name(),'#292321')
                def save_editor():
                    editor=self.app.activeModalWidget()
                    editor.findChild(QPushButton,'color-output').click()
                    editor.accept()
                with patch.object(QColorDialog,'getColor',return_value=QColor('#e2d3c0')):
                    QTimer.singleShot(0,save_editor)
                    self.assertTrue(w.edit_custom_theme())
                self.assertEqual(w.theme_name,'custom')
                self.assertEqual(w.operation_output.palette().base().color().name(),'#e2d3c0')
                self.assertEqual(w.custom_colors['text'],'#292321')
            finally:
                self.wait_scan(w); w.close(); self.app.processEvents()
            restored=Window(QSettings(config,QSettings.IniFormat)); restored.show()
            try:
                self.wait_scan(restored)
                self.assertEqual(restored.theme_name,'custom')
                self.assertEqual(restored.custom_colors['output'],'#e2d3c0')
                self.assertEqual(restored.operation_output.palette().base().color().name(),'#e2d3c0')
                def cancel_editor():
                    editor=self.app.activeModalWidget(); editor.colors['output']='#112233'; editor.reject()
                QTimer.singleShot(0,cancel_editor)
                self.assertFalse(restored.edit_custom_theme())
                self.assertEqual(restored.custom_colors['output'],'#e2d3c0')
                def select_dark():
                    self.app.activeModalWidget().findChild(QPushButton,'theme-dark').click()
                QTimer.singleShot(0,select_dark); restored.toggle_theme()
                self.assertEqual(restored.theme_name,'dark')
                self.assertEqual(restored.settings.value('theme/selected'),'dark')
                self.assertEqual(restored.custom_colors['output'],'#e2d3c0')
            finally:
                self.wait_scan(restored); restored.close(); self.app.processEvents()

    def test_invalid_saved_colors_fall_back_to_dark_defaults(self):
        with tempfile.TemporaryDirectory() as tmp, patch('packscope.app.scan_all',return_value=[]):
            settings=QSettings(str(Path(tmp)/'settings.ini'),QSettings.IniFormat)
            settings.setValue('theme/selected','custom')
            settings.setValue('theme/custom','{"bg":"; bad css"}')
            w=Window(settings)
            try:
                self.wait_scan(w)
                self.assertEqual(w.custom_colors['bg'],'#1b191b')
                self.assertEqual(w.operation_output.palette().base().color().name(),'#111111')
            finally:
                self.wait_scan(w); w.close(); self.app.processEvents()


if __name__ == '__main__': unittest.main()
