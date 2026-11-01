import os
import tempfile
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QMessageBox
from packscope.app import Window
from packscope.inventory import Package, ScanResult
from packscope.launch import LaunchTarget


class LaunchUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        config=tempfile.TemporaryDirectory()
        self.addCleanup(config.cleanup)
        self.settings=QSettings(str(Path(config.name)/'settings.ini'),QSettings.IniFormat)

    def wait_for(self, condition, timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.app.processEvents()
            if condition(): return
            time.sleep(.01)
        self.fail('等待介面背景作業逾時')

    def test_stale_launcher_result_cannot_enable_wrong_selection(self):
        first=Package('First','first','1','APT / dpkg','系統',is_application=True)
        second=Package('Second','second','1','APT / dpkg','系統',is_application=True)
        entered=threading.Event(); release=threading.Event(); second_seen=threading.Event()
        def find(package):
            if package.ident=='first':
                entered.set(); release.wait(3)
                return [LaunchTarget('First','desktop','/tmp/first.desktop')]
            second_seen.set(); return []
        with patch('packscope.app.scan_all',return_value=[ScanResult('APT / dpkg',[first,second],'ok')]), \
             patch('packscope.launch.find_targets',side_effect=find), \
             patch.object(QMessageBox,'information') as help_box:
            window=Window(self.settings); window.show()
            try:
                self.wait_for(lambda:window.thread is None)
                self.assertFalse(hasattr(window,'preview_button'))
                window.show_sources_help(); text=help_box.call_args.args[2]
                for source in ('.deb','Snap','Flatpak','AppImage','pipx','npm global','Cargo'):
                    self.assertIn(source,text)
                self.assertIn('不一定能確定',text)
                window.search.setText('first'); window.table.selectRow(0)
                self.wait_for(entered.is_set)
                window.search.setText('second'); window.table.selectRow(0)
                self.wait_for(second_seen.is_set)
                release.set(); self.wait_for(lambda:not window.jobs)
                self.assertFalse(window.open_button.isEnabled())
                self.assertEqual(window.launch_targets,[])
            finally:
                release.set(); self.wait_for(lambda:not window.jobs); window.close(); self.app.processEvents()

if __name__=='__main__': unittest.main()
