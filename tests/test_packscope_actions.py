import subprocess
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from packscope import actions
from packscope.inventory import Package

def package(manager, ident, scope='系統'):
    return Package(ident, ident, '1', manager, scope)

class ActionTests(unittest.TestCase):
    @patch('packscope.actions.shutil.which',side_effect=lambda s:'/usr/bin/'+s)
    def test_local_package_formats_use_correct_manager_and_file_argument(self, which):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            cases=[('Some package.DEB','APT / dpkg',('install','--',)),
                   ('Some package.snap','Snap',('install','--dangerous','--')),
                   ('Some package.flatpak','Flatpak',('--bundle','--')),
                   ('Some package.flatpakref','Flatpak',('--from','--')),
                   ('Some package.AppImage','AppImage',())]
            for name, manager, ending in cases:
                with self.subTest(name=name):
                    path=root/name; path.write_bytes(b'fixture')
                    op=actions.make_file_install(str(path))
                    self.assertEqual(op.package.manager,manager)
                    self.assertEqual(op.package.location,str(path))
                    if ending:
                        self.assertEqual(op.argv[-len(ending)-1:-1],ending)
                        self.assertEqual(op.argv[-1],str(path))
                    else: self.assertEqual(op.argv,())
                    self.assertEqual(op.needs_auth,manager in ('APT / dpkg','Snap'))
            unknown=root/'something.zip'; unknown.touch()
            with self.assertRaisesRegex(ValueError,'不支援'): actions.make_file_install(str(unknown))
            with self.assertRaisesRegex(ValueError,'找不到'): actions.make_file_install(str(root/'missing.deb'))

    @patch('packscope.actions.shutil.which',side_effect=lambda s:'/usr/bin/'+s)
    def test_apt_operations_use_pkexec_and_separate_arguments(self, which):
        for action, expected in [('install','install'),('remove','remove'),('update','install')]:
            op=actions.make_operation(package('APT / dpkg','example:amd64'),action)
            self.assertEqual(op.argv[0],'/usr/bin/pkexec')
            self.assertIn(expected,op.argv)
            self.assertEqual(op.argv[-2:],('--','example:amd64'))
            self.assertTrue(op.needs_auth)
        with self.assertRaises(ValueError): actions.make_operation(package('APT / dpkg','x;touch /tmp/evil'),'remove')

    @patch('packscope.actions.subprocess.run')
    @patch('packscope.actions.shutil.which',return_value='/usr/bin/apt-get')
    def test_apt_preview_parses_install_upgrade_removal_and_summary(self, which, run):
        output=('Inst new-tool (2.0 Ubuntu:24.04 [amd64])\n'
                'Inst old-tool [1.0] (1.1 Ubuntu:24.04 [amd64])\n'
                'Remv obsolete-tool [3.0]\n'
                '2 upgraded, 1 newly installed, 1 to remove and 0 not upgraded.\n')
        run.return_value=subprocess.CompletedProcess([],0,stdout=output,stderr='')
        op=actions.Operation('remove',package('APT / dpkg','old-tool'),('/usr/bin/pkexec',),True)
        preview=actions.preview_operation(op)
        self.assertTrue(preview.available)
        self.assertEqual(preview.changes,('安裝：new-tool → 2.0','版本變更：old-tool 1.0 → 1.1','移除：obsolete-tool 3.0'))
        self.assertIn('2 upgraded',preview.summary)
        args=run.call_args.args[0]
        self.assertEqual(args[0],'/usr/bin/apt-get')
        self.assertIn('-s',args)
        self.assertEqual(args[-3:],['remove','--','old-tool'])
        self.assertEqual(run.call_args.kwargs['stdin'],subprocess.DEVNULL)
        self.assertEqual(run.call_args.kwargs['env']['LC_ALL'],'C')
        self.assertNotIn('pkexec',args)

    @patch('packscope.actions.subprocess.run')
    @patch('packscope.actions.shutil.which',return_value='/usr/bin/apt-get')
    def test_apt_batch_preview_combines_targets_and_local_deb_uses_file_path(self, which, run):
        run.return_value=subprocess.CompletedProcess([],0,stdout='Inst one (2 repo)\nInst two (3 repo)\n',stderr='')
        operations=[actions.Operation('update',package('APT / dpkg',name),(),True) for name in ('one','two')]
        preview=actions.preview_operations(operations)
        self.assertEqual(preview.changes,('安裝：one → 2','安裝：two → 3'))
        self.assertEqual(run.call_args.args[0][-4:],['--only-upgrade','--','one','two'])
        with tempfile.TemporaryDirectory() as tmp:
            deb=Path(tmp)/'local package.deb'; deb.touch()
            op=actions.Operation('install',Package(deb.stem,str(deb),'未知','APT / dpkg','系統',location=str(deb)),(),True)
            actions.preview_operation(op)
            args=run.call_args.args[0]
            self.assertEqual(args[-3:],['install','--',str(deb.resolve())])

    @patch('packscope.actions.subprocess.run',side_effect=subprocess.TimeoutExpired('apt-get',90))
    @patch('packscope.actions.shutil.which',return_value='/usr/bin/apt-get')
    def test_apt_preview_timeout_is_explicit_and_does_not_fail_the_ui(self, which, run):
        op=actions.Operation('remove',package('APT / dpkg','example'),(),True)
        preview=actions.preview_operation(op,timeout=90)
        self.assertFalse(preview.available)
        self.assertIn('timed out',preview.warning.lower())

    @patch('packscope.actions.shutil.which',side_effect=lambda s:'/usr/bin/'+s)
    def test_snap_flatpak_and_developer_commands(self, which):
        snap=actions.make_operation(package('Snap','firefox'),'update')
        self.assertEqual(snap.argv,('/usr/bin/pkexec','/usr/bin/snap','refresh','--','firefox'))
        flat=actions.make_operation(package('Flatpak','org.test.App/x86_64/stable','使用者'),'remove')
        self.assertEqual(flat.argv[-2:],('--','org.test.App/x86_64/stable'))
        self.assertFalse(flat.needs_auth)
        npm=actions.make_operation(package('npm global','@test/tool','使用者'),'remove')
        self.assertEqual(npm.argv,('/usr/bin/npm','uninstall','--global','--','@test/tool'))
        pipx=actions.make_operation(Package('tool','tool','1','pipx','使用者',location='/home/u/.local/share/pipx/venvs/tool-test'),'remove')
        self.assertEqual(pipx.argv[-1],'tool-test')
        flat_install=actions.make_operation(package('Flatpak','org.test.App','系統'),'install','flathub')
        self.assertTrue(flat_install.needs_auth)
        self.assertNotIn('--noninteractive',flat_install.argv)
        self.assertEqual(flat_install.argv[-3:],('--','flathub','org.test.App'))
        with self.assertRaises(ValueError): actions.make_operation(package('Snap','../../evil'),'remove')

    @patch('packscope.actions.subprocess.Popen')
    def test_execution_does_not_use_shell_and_surfaces_errors(self, run):
        op=actions.Operation('remove',package('Snap','test'),('/usr/bin/pkexec','/usr/bin/snap','remove','--','test'),True)
        class Stream:
            def __init__(self,lines): self.lines=lines
            def __iter__(self): return iter(self.lines)
            def close(self): pass
        class Process:
            def __init__(self,lines,code): self.stdout=Stream(lines); self.code=code
            def wait(self): return self.code
        run.return_value=Process(['done\n'],0)
        self.assertEqual(actions.execute(op),'done')
        self.assertNotIn('shell',run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs['stdin'],subprocess.DEVNULL)
        run.return_value=Process(['authentication cancelled\n'],126)
        with self.assertRaisesRegex(RuntimeError,'authentication cancelled'): actions.execute(op)

    @patch('packscope.actions.check_dpkg_health')
    def test_streams_output_before_process_finishes_and_parses_real_progress(self, health):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); script=root/'fixture.py'; release=root/'release'
            script.write_text('#!/usr/bin/env python3\nimport pathlib,sys,time\n'
                              'print("pmstatus:example:25.0:working",flush=True)\n'
                              'while not pathlib.Path(sys.argv[1]).exists(): time.sleep(0.02)\n'
                              'print("pmstatus:example:100.0:done",flush=True)\n')
            script.chmod(0o755); output=[]; progress=[]; first=threading.Event(); result=[]
            def received(line): output.append(line); first.set()
            op=actions.Operation('remove',package('APT / dpkg','example'),(str(script),str(release)),False)
            worker=threading.Thread(target=lambda:result.append(actions.execute(op,received,progress.append)))
            worker.start()
            try:
                self.assertTrue(first.wait(3),'first output was not delivered while running')
                self.assertTrue(worker.is_alive())
            finally:
                release.touch(); worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertEqual(progress,[25,99])
            self.assertIn('done',result[0])
            self.assertIsNone(actions.progress_value('installed version 1.2.3','APT / dpkg'))

    @patch('packscope.actions.subprocess.run')
    @patch('packscope.actions.shutil.which',return_value='/usr/bin/dpkg-query')
    def test_dpkg_preflight_blocks_incomplete_packages(self, which, run):
        run.return_value=subprocess.CompletedProcess([],0,stdout='google-chrome-stable\thalf-configured\nlauncher\tinstalled\n',stderr='')
        with self.assertRaisesRegex(RuntimeError,'google-chrome-stable.*half-configured'):
            actions.check_dpkg_health()
        run.return_value=subprocess.CompletedProcess([],0,stdout='launcher\tinstalled\n',stderr='')
        actions.check_dpkg_health()

    @patch('packscope.actions.subprocess.Popen')
    @patch('packscope.actions.check_dpkg_health',side_effect=RuntimeError('dpkg 問題'))
    def test_apt_does_not_start_when_dpkg_is_unhealthy(self, health, popen):
        op=actions.Operation('update',package('APT / dpkg','example'),('/usr/bin/apt-get',),True)
        with self.assertRaisesRegex(RuntimeError,'dpkg 問題'): actions.execute(op)
        popen.assert_not_called()

    @patch('packscope.actions.subprocess.run')
    @patch('packscope.actions.shutil.which',return_value='/usr/bin/apt-cache')
    def test_apt_search_uses_literal_input(self, which, run):
        run.return_value=subprocess.CompletedProcess([],0,stdout='7zip - Archive tool\n',stderr='')
        self.assertEqual(actions.search_apt('7zip'),[('7zip','Archive tool')])
        self.assertEqual(run.call_args.args[0][-2:],['--','7zip'])
        self.assertNotIn('shell',run.call_args.kwargs)

    def test_appimage_install_and_matching_desktop_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); home=root/'home'; home.mkdir(); source=root/'Example.AppImage'; source.write_bytes(b'fixture')
            with patch.dict(os.environ,{'HOME':str(home)}):
                p=Package('Example',str(source),'未知','AppImage','使用者',location=str(source))
                op=actions.make_operation(p,'install'); actions.execute(op)
                installed=home/'Applications'/'Example.AppImage'; self.assertEqual(installed.read_bytes(),b'fixture')
                desktop=actions._appimage_desktop(installed); self.assertIn('X-PackScope-Target=',desktop.read_text())
                with patch('packscope.actions.shutil.which',return_value='/usr/bin/gio'):
                    installed_package=Package('Example',str(installed),'未知','AppImage','使用者',location=str(installed))
                    removal=actions.make_operation(installed_package,'remove')
                self.assertEqual(removal.argv[-2:],(str(installed),str(desktop)))

if __name__ == '__main__': unittest.main()
