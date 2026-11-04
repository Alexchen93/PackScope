import os
import time
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt5.QtCore import QSettings, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox, QFileDialog, QComboBox
from packscope.app import Window
from packscope.actions import OperationPreview
from packscope.inventory import Package, ScanResult

class OutputUITests(unittest.TestCase):
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

    def test_opened_installer_uses_detected_manager_without_file_picker(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'example package.snap'; path.write_bytes(b'fixture')
            with patch('packscope.app.scan_all',return_value=[]), \
                 patch('packscope.actions.shutil.which',side_effect=lambda name:'/usr/bin/'+name), \
                 patch.object(QFileDialog,'getOpenFileName') as choose:
                w=Window(self.settings)
                try:
                    with patch.object(w,'perform_operation') as perform:
                        w.install_file(str(path))
                    choose.assert_not_called()
                    operation=perform.call_args.kwargs['operation']
                    self.assertEqual(operation.package.manager,'Snap')
                    self.assertEqual(operation.package.location,str(path))
                    self.assertEqual(operation.argv[-1],str(path))
                finally:
                    self.wait_for(lambda:w.thread is None)
                    w.close(); self.app.processEvents()

    def test_install_button_selects_file_and_refreshes_installed_list(self):
        installed=Package('example','example','1','APT / dpkg','系統',is_application=True)
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
                  patch('packscope.actions.preview_operation',return_value=OperationPreview(True,('安裝：example → 1',))), \
                  patch('packscope.actions.execute',side_effect=execute), \
                  patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')) as choose, \
                  patch.object(QMessageBox,'exec_',return_value=QMessageBox.Yes):
                w=Window(self.settings); w.show()
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
        installed=Package('example','example','1','APT / dpkg','系統',is_application=True)
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
             patch('packscope.actions.preview_operation',return_value=OperationPreview(True,('安裝：example → 1',))), \
             patch('packscope.actions.execute',return_value='done'), \
             patch.object(QFileDialog,'getOpenFileName',return_value=(str(path),'')), \
             patch.object(QMessageBox,'exec_',return_value=QMessageBox.Yes):
                w=Window(self.settings); w.show()
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

    def test_details_align_indented_metadata_at_the_left_edge(self):
        p=Package('Example','org.example.App/x86_64/stable','1','Flatpak','使用者')
        metadata='Flatpak 已安裝資料\n\n  ID: org.example.App\n    Ref: app/org.example.App/x86_64/stable\n\n    Commit: abc123\n'
        with patch('packscope.app.scan_all',return_value=[ScanResult('Flatpak',[p],'ok')]), \
             patch('packscope.backend.details',return_value=metadata):
            w=Window(self.settings); w.show(); shown=[]
            try:
                self.wait_for(lambda:w.thread is None)
                w.selected_package=lambda:p
                w.text_dialog=lambda title,content:shown.append((title,content))
                w.show_more(); self.wait_for(lambda:not w.jobs)
                self.assertEqual(shown[0][1], 'Flatpak 已安裝資料\n\nID: org.example.App\nRef: app/org.example.App/x86_64/stable\n\nCommit: abc123')
            finally:
                self.wait_for(lambda:not w.jobs and w.thread is None)
                w.close(); self.app.processEvents()

    def test_source_dialog_selection_and_cancellation_in_both_themes(self):
        with patch('packscope.app.scan_all',return_value=[]):
            w=Window(self.settings); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                w.set_theme('dark',persist=False)
                for dark in (True,False):
                    if not dark: w.set_theme('light',persist=False)
                    def accept_snap():
                        dialog=self.app.activeModalWidget(); combo=dialog.findChild(QComboBox)
                        combo.showPopup(); self.app.processEvents()
                        self.assertEqual(combo.view().window().palette().window().color().name(), '#252225' if dark else '#fffdfa')
                        combo.hidePopup(); combo.setCurrentText('Snap'); dialog.accept()
                    QTimer.singleShot(0,accept_snap)
                    self.assertEqual(w.choose_install_source(),('Snap',True))
                    QTimer.singleShot(0,lambda:self.app.activeModalWidget().reject())
                    self.assertFalse(w.choose_install_source()[1])
            finally:
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
              patch('packscope.actions.preview_operation',return_value=OperationPreview(True,('更新：example 1 → 2',))), \
              patch('packscope.actions.execute',side_effect=execute), \
              patch.object(QMessageBox,'exec_',return_value=QMessageBox.Yes):
            w=Window(self.settings); w.resize(920,580); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                self.assertTrue(w.operation_panel.isVisible())
                self.assertEqual(w.operation_output.toPlainText(),'')
                self.assertEqual(w.operation_bar.value(),0)
                self.assertFalse(w.operation_bar.isVisible())
                self.assertFalse(hasattr(w,'operation_title'))
                self.assertFalse(hasattr(w,'operation_percent'))
                self.assertFalse(hasattr(w,'output_toggle'))
                self.assertGreater(w.sources_help_button.x(),w.source_combo.x())
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
                w.show_updates=lambda result:None
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

    def test_idle_operation_warning_and_close_request_are_actionable(self):
        with patch('packscope.app.scan_all',return_value=[]):
            w=Window(self.settings); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                w.operation_idle_warning_seconds=0
                w.start_operation_monitor('測試套件操作')
                w.operation_last_output_at=time.monotonic()-2
                w.check_operation_activity()
                self.assertIn('沒有新輸出',w.status.text())
                self.assertIn('授權視窗',w.status.text())

                class RunningTask:
                    def isRunning(self): return True
                task=RunningTask(); w.jobs.add(task)
                w.operation_busy=True
                w.close(); self.app.processEvents()
                self.assertTrue(w.isVisible())
                self.assertIn('套件作業仍在執行',w.status.text())
                w.jobs.remove(task)
                w.operation_busy=False
                w.stop_operation_monitor()
            finally:
                w.jobs.clear(); w.stop_operation_monitor()
                w.operation_busy=False
                w.close(); self.app.processEvents()

    def test_apt_lock_failure_explains_system_update_and_retry(self):
        package=Package('Example','example','1','APT / dpkg','系統')
        operation=SimpleNamespace(action='remove',package=package,argv=('/usr/bin/apt-get',),needs_auth=False)
        error=('操作未完成（代碼 100）。\n\nE: Could not get lock /var/lib/dpkg/lock-frontend. '
               'It is held by process 15121 (unattended-upgr)')
        with patch('packscope.app.scan_all',return_value=[ScanResult('APT / dpkg',[package],'ok')]), \
             patch('packscope.actions.make_operation',return_value=operation), \
             patch('packscope.actions.preview_operation',return_value=OperationPreview(True)), \
             patch('packscope.actions.execute',side_effect=RuntimeError(error)), \
             patch.object(QMessageBox,'exec_',return_value=QMessageBox.Yes), \
             patch.object(QMessageBox,'warning') as warning:
            w=Window(self.settings); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                w.perform_operation(package,'remove')
                self.wait_for(lambda:not w.operation_busy and not w.jobs and w.thread is None)
                explanation='Ubuntu 自動更新程序（PID 15121）'
                self.assertIn(explanation,w.operation_output.toPlainText())
                self.assertIn('完成後再重試',w.operation_output.toPlainText())
                self.assertIn('APT／dpkg 正忙碌',w.status.text())
                warning.assert_called_once()
                self.assertIn(explanation,warning.call_args.args[2])
            finally:
                self.wait_for(lambda:not w.jobs and w.thread is None)
                w.close(); self.app.processEvents()

    def test_failed_apt_preview_is_explicit_and_declining_never_runs_operation(self):
        package=Package('Example','example','1','APT / dpkg','系統')
        with patch('packscope.app.scan_all',return_value=[ScanResult('APT / dpkg',[package],'ok')]), \
             patch('packscope.actions.shutil.which',side_effect=lambda name:'/usr/bin/'+name), \
             patch('packscope.actions.preview_operation',return_value=OperationPreview(False,warning='模擬逾時')), \
             patch('packscope.actions.execute') as execute, \
             patch.object(QMessageBox,'exec_',return_value=QMessageBox.No):
            w=Window(self.settings); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                w.perform_operation(package,'remove')
                self.wait_for(lambda:not w.operation_busy and not w.jobs)
                execute.assert_not_called()
                self.assertIn('已取消移除',w.status.text())
                self.assertIn('無法取得 APT 變更預覽',w.operation_output.toPlainText())
            finally:
                self.wait_for(lambda:not w.jobs and w.thread is None)
                w.close(); self.app.processEvents()

if __name__=='__main__': unittest.main()
