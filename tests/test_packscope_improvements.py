import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt5.QtCore import QSettings, QTimer, Qt
from PyQt5.QtWidgets import QApplication, QMessageBox, QPushButton, QTableWidget
from packscope import actions, backend, inventory
from packscope.actions import OperationPreview
from packscope.app import Window, Filter, Model
from packscope.inventory import Package, ScanResult


class ImprovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        config=tempfile.TemporaryDirectory()
        self.addCleanup(config.cleanup)
        self.settings=QSettings(str(Path(config.name)/'settings.ini'),QSettings.IniFormat)
    def wait_for(self,condition,timeout=4):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            self.app.processEvents()
            if condition(): return
            time.sleep(.01)
        self.fail('等待背景作業逾時')

    def test_appimage_real_copy_and_inventory_distinguish_download_and_managed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{'HOME':tmp}):
            root=Path(tmp); downloads=root/'Downloads'; downloads.mkdir()
            source=downloads/'Example.AppImage'; source.write_bytes(b'fixture')
            actions.install_appimage(source)
            rows=inventory.appimage().packages
            by_path={p.location:p for p in rows}
            managed=by_path[str(root/'Applications'/'Example.AppImage')]
            self.assertEqual(managed.appimage_state,'PackScope 管理')
            self.assertEqual(by_path[str(source)].appimage_state,'偵測到檔案')
            self.assertTrue(managed.is_application)

    def test_desktop_detection_and_application_filter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); desktop=root/'app.desktop'
            desktop.write_text('[Desktop Entry]\nType=Application\nName=Example App\nIcon=example\n')
            (root/'example.list').write_text(str(desktop)+'\n')
            # A desktop entry must be in an applications directory.
            folder=root/'applications'; folder.mkdir(); desktop.rename(folder/'app.desktop')
            (root/'example.list').write_text(str(folder/'app.desktop')+'\n')
            self.assertEqual(inventory.debian_desktop_entries(root)['example'],('Example App','example'))
        model=Model(); model.replace([Package('App','app','1','APT / dpkg',is_application=True),Package('lib','lib','1','APT / dpkg')])
        proxy=Filter(); proxy.setSourceModel(model); self.assertEqual(proxy.rowCount(),2)
        proxy.set_applications_only(True); self.assertEqual(proxy.rowCount(),1); self.assertEqual(proxy.index(0,0).data(),'App')
        proxy.set_applications_only(False); self.assertEqual(proxy.rowCount(),2)

    def test_update_mapping_preserves_sources_and_flatpak_scopes(self):
        apt=Package('Editor','editor','1','APT / dpkg','系統')
        snap=Package('Editor','editor','2','Snap','系統')
        fpuser=Package('Flat Editor','org.example.Editor/x86_64/stable','3','Flatpak','使用者')
        fpsystem=Package('Flat Editor','org.example.Editor/x86_64/stable','4','Flatpak','系統')
        sections=[('APT / dpkg','',['editor  1 → 1.1'],None),('Snap','',['editor 2.1 10 1MB dev -'],None),
                  ('Flatpak','',['app/org.example.Editor/x86_64/stable  ·  flathub'],None),
                  ('APT / dpkg','',['unknown  1 → 2'],None)]
        items=backend.update_items(sections,[apt,snap,fpuser,fpsystem])
        self.assertEqual([i.package for i in items],[apt,snap,fpuser,fpsystem,None])
        self.assertEqual(items[0].candidate,'1.1'); self.assertEqual(items[1].candidate,'2.1')
        self.assertEqual([items[2].current,items[3].current],['3','4'])
        scoped=backend.update_items([('Flatpak / 使用者','',['app/org.example.Editor/x86_64/stable  ·  flathub  ·  5'],None)],[fpuser,fpsystem])
        self.assertEqual([item.package for item in scoped],[fpuser])
        self.assertEqual(scoped[0].candidate,'5')
        native=Package('Library','libexample:amd64','1','APT / dpkg','系統')
        foreign=Package('Library','libexample:i386','1','APT / dpkg','系統')
        with patch('packscope.backend.command',return_value=subprocess.CompletedProcess([],0,'amd64\n','')):
            resolved=backend.update_items([('APT / dpkg','',['libexample  1 → 2'],None)],[native,foreign])
        self.assertEqual(resolved[0].package,native)

    def test_metadata_refresh_commands_cover_apt_and_both_flatpak_scopes(self):
        with patch('packscope.actions.shutil.which',side_effect=lambda s:'/usr/bin/'+s):
            ops=actions.metadata_operations()
        self.assertEqual(ops[0].argv,('/usr/bin/pkexec','/usr/bin/apt-get','update'))
        self.assertEqual(ops[1].argv,('/usr/bin/flatpak','update','--user','--appstream','-y'))
        self.assertEqual(ops[2].argv,('/usr/bin/flatpak','update','--system','--appstream','-y'))

    def test_update_dialog_selects_only_checked_and_batch_continues_after_error(self):
        first=Package('First','first','1','APT / dpkg','系統')
        second=Package('Second','second','1','APT / dpkg','系統')
        sections=[('APT / dpkg','local',['first  1 → 2','second  1 → 2'],None)]
        seen=[]
        def execute(op,on_output,on_progress):
            seen.append(op.package.ident); on_output('test output')
            if op.package.ident=='first': raise RuntimeError('test failure')
            return 'ok'
        with patch('packscope.app.scan_all',return_value=[ScanResult('APT / dpkg',[first,second],'ok')]), \
             patch('packscope.actions.shutil.which',side_effect=lambda name:'/usr/bin/'+name), \
             patch('packscope.actions.preview_operations',return_value=OperationPreview(True,('更新：first 1 → 2','更新：second 1 → 2'))), \
             patch('packscope.actions.execute',side_effect=execute), \
             patch.object(QMessageBox,'exec_',return_value=QMessageBox.Yes), \
             patch.object(QMessageBox,'warning'):
            w=Window(self.settings); w.show()
            try:
                self.wait_for(lambda:w.thread is None)
                def choose():
                    d=self.app.activeModalWidget(); table=d.findChild(QTableWidget)
                    table.item(0,0).setCheckState(Qt.Checked); table.item(1,0).setCheckState(Qt.Checked)
                    next(b for b in d.findChildren(QPushButton) if b.text()=='更新選取項目').click()
                QTimer.singleShot(0,choose); w.show_updates(sections)
                self.wait_for(lambda:not w.operation_busy and not w.jobs and w.thread is None)
                self.assertEqual(seen,['first','second'])
                self.assertIn('失敗 1 項',w.operation_output.toPlainText())
            finally:
                self.wait_for(lambda:not w.jobs and w.thread is None); w.close(); self.app.processEvents()

if __name__=='__main__': unittest.main()
