import os
import time
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog
from packscope.app import Window
from packscope.inventory import Package, ScanResult

class OutputUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def wait_for(self, condition, timeout=4):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            self.app.processEvents()
            if condition(): return
            time.sleep(.01)
        self.fail('等待介面背景作業逾時')

    def test_install_button_selects_file_and_refreshes_installed_list(self):
        installed=Package('example','example','1','APT / dpkg','系統')
        state={'installed':False}
        def scan():
            return [ScanResult('APT / dpkg',[installed] if state['installed'] else [],'ok')]
        def execute(op,on_output,on_progress):
            self.assertEqual(op.package.manager,'APT / dpkg')
            on_output('fixture installed'); on_progress(50); state['installed']=True
            return 'done'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'my package.deb'; path.write_bytes(b'fixture')
            with patch('packscope.app.scan_all',side_effect=scan), \
                 patch('packscope.actions.shutil.which',side_effect=lambda s:'/usr/bin/'+s), \
                 patch('packscope.actions.execute',side_effect=execute), \
                 patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')) as choose, \
                 patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
                w=Window(); w.show()
                try:
                    self.wait_for(lambda:w.thread is None)
                    w.search.setText('not the package'); w.select_manager('Snap')
                    w.install_button.click()
                    self.wait_for(lambda:not w.operation_busy and not w.jobs and w.thread is None)
                    choose.assert_called_once()
                    self.assertEqual(choose.call_args.kwargs['options'],QFileDialog.DontUseNativeDialog)
                    self.assertEqual(w.search.text(),'')
                    self.assertEqual(w.proxy.manager,'APT / dpkg')
                    self.assertEqual(w.proxy.rowCount(),1)
                    self.assertEqual(w.proxy.index(0,0).data(),'example')
                    self.assertIn('fixture installed',w.operation_output.toPlainText())
                    self.assertEqual(w.operation_bar.value(),100)
                    self.assertEqual(w.install_button.menu().actions()[0].text(),'依名稱安裝')
                finally:
                    self.wait_for(lambda:not w.jobs and w.thread is None)
                    w.close(); self.app.processEvents()

    def test_install_finishing_during_scan_triggers_another_scan(self):
        released=threading.Event(); state={'calls':0}
        installed=Package('example','example','1','APT / dpkg','系統')
        def scan():
            state['calls']+=1
            if state['calls']==1:
                released.wait(3)
                return [ScanResult('APT / dpkg',[],'ok')]
            return [ScanResult('APT / dpkg',[installed],'ok')]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'example.deb'; path.write_bytes(b'fixture')
            with patch('packscope.app.scan_all',side_effect=scan), \
                 patch('packscope.actions.shutil.which',side_effect=lambda s:'/usr/bin/'+s), \
                 patch('packscope.actions.execute',return_value='done'), \
                 patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')), \
                 patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
                w=Window(); w.show()
                try:
                    w.install_button.click()
                    self.wait_for(lambda:not w.operation_busy and not w.jobs)
                    self.assertTrue(w.refresh_after_scan)
                    released.set()
                    self.wait_for(lambda:w.thread is None and state['calls']>=2)
                    self.assertEqual(w.proxy.rowCount(),1)
                finally:
                    released.set()
                    self.wait_for(lambda:not w.jobs and w.thread is None)
                    w.close(); self.app.processEvents()

    def test_empty_at_start_and_keeps_multiple_actions_and_refresh(self):
        first=Package('First','first','1','APT / dpkg','系統')
        second=Package('Second','second','1','APT / dpkg','系統')
        def make_op(package,action,remote):
            return SimpleNamespace(action=action,package=package,argv=('/fixture',package.ident),needs_auth=False)
        def execute(op,on_output,on_progress):
            on_output('fixture output '+op.package.ident); on_progress(25); return 'done'
        with patch('packscope.app.scan_all',return_value=[ScanResult('APT / dpkg',[first,second],'ok')]), \
             patch('packscope.actions.make_operation',side_effect=make_op), \
             patch('packscope.actions.execute',side_effect=execute), \
             patch.object(QMessageBox,'question',return_value=QMessageBox.Yes):
            w=Window(); w.resize(920,580); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                self.assertTrue(w.operation_panel.isVisible())
                self.assertEqual(w.operation_output.toPlainText(),'')
                self.assertEqual(w.operation_bar.value(),0)
                self.assertFalse(w.operation_bar.isVisible())
                self.assertFalse(hasattr(w,'operation_title'))
                self.assertFalse(hasattr(w,'operation_percent'))
                self.assertFalse(hasattr(w,'output_toggle'))
                self.assertEqual(w.sources_help_button.size(),w.buttons['Snap'].size())
                self.assertGreater(w.sources_help_button.x(),w.buttons['開發工具'].x())
                self.assertEqual(w.sources_help_button.y(),w.buttons['開發工具'].y())
                w.perform_operation(first,'remove')
                self.wait_for(lambda:not w.operation_busy and not w.jobs and w.thread is None)
                self.assertTrue(w.operation_bar.isVisible())
                self.assertIn('fixture output first',w.operation_output.toPlainText())
                w.perform_operation(second,'update')
                self.wait_for(lambda:not w.operation_busy and not w.jobs and w.thread is None)
                history=w.operation_output.toPlainText()
                self.assertIn('fixture output first',history)
                self.assertIn('fixture output second',history)
                self.assertLess(history.index('fixture output first'),history.index('fixture output second'))
                self.assertEqual(w.operation_bar.value(),100)
                w.manual_refresh(); self.wait_for(lambda:w.thread is None)
                history=w.operation_output.toPlainText()
                self.assertIn('重新掃描完成',history)
                self.assertIn('fixture output first',history)
                w.text_dialog=lambda title,text:None
                with patch('packscope.backend.check_updates',return_value=[('APT / dpkg','', ['example'],None),('AppImage','尚未檢查',[],None)]):
                    w.check_updates(); self.wait_for(lambda:not w.jobs)
                history=w.operation_output.toPlainText()
                self.assertIn('更新查詢完成',history)
                self.assertIn('APT / dpkg 1 項',history)
                self.assertIn('AppImage 尚未檢查',history)
                self.assertIn('fixture output first',history)
            finally:
                self.wait_for(lambda:not w.jobs and w.thread is None)
                w.close(); self.app.processEvents()

if __name__=='__main__': unittest.main()
