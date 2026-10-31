import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from packscope import launch
from packscope.inventory import Package


def pkg(manager, ident, scope='系統', location=''):
    return Package('Example', ident, '1', manager, scope, location=location)


class LaunchTests(unittest.TestCase):
    def test_apt_discovers_desktop_entry_and_opens_only_when_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); marker=root/'opened'; executable=root/'fixture'
            executable.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("opened")\n')
            executable.chmod(0o755)
            desktop=root/'example.desktop'
            desktop.write_text('[Desktop Entry]\nType=Application\nName=Fixture\nExec='+str(executable)+'\nTerminal=false\n')
            result=subprocess.CompletedProcess([],0,stdout=str(desktop)+'\n',stderr='')
            with patch('packscope.launch.command',return_value=result) as query:
                targets=launch.find_targets(pkg('APT / dpkg','example'))
            self.assertEqual(query.call_args.args[0],['dpkg-query','-L','--','example'])
            self.assertEqual(len(targets),1)
            self.assertFalse(marker.exists())
            self.assertEqual(launch.start_target(targets[0]),'已送出開啟要求。')
            deadline=time.monotonic()+3
            while not marker.exists() and time.monotonic()<deadline: time.sleep(.02)
            self.assertTrue(marker.exists())

    @patch('packscope.launch.command')
    @patch('packscope.launch.shutil.which',return_value='/usr/bin/flatpak')
    def test_flatpak_application_is_openable_but_runtime_is_not(self, which, command):
        command.return_value=subprocess.CompletedProcess([],0,stdout='app/org.test.App/x86_64/stable\n',stderr='')
        p=pkg('Flatpak','org.test.App/x86_64/stable','使用者')
        targets=launch.find_targets(p)
        self.assertEqual(targets[0].argv,('/usr/bin/flatpak','run','--user','--arch=x86_64','--branch=stable','org.test.App'))
        command.return_value=subprocess.CompletedProcess([],0,stdout='runtime/org.test.App/x86_64/stable\n',stderr='')
        self.assertEqual(launch.find_targets(p),[])

    @patch('packscope.launch._desktop_target')
    @patch('packscope.launch._snap_apps')
    def test_snap_skips_daemons_and_non_desktop_commands(self, apps, desktop):
        apps.return_value=[{'snap':'example','name':'example','desktop-file':'/tmp/app.desktop'},
                           {'snap':'example','name':'server','desktop-file':'/tmp/server.desktop','daemon':'simple'},
                           {'snap':'example','name':'cli'}]
        desktop.return_value=launch.LaunchTarget('Example','desktop','/tmp/app.desktop')
        result=launch.find_targets(pkg('Snap','example'))
        self.assertEqual(len(result),1)
        desktop.assert_called_once_with('/tmp/app.desktop')

    @patch('packscope.launch.subprocess.Popen')
    def test_executable_appimage_launches_without_shell(self, popen):
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'Example.AppImage'; image.write_text('fixture')
            p=pkg('AppImage',str(image),'使用者',str(image))
            image.chmod(0o644); self.assertEqual(launch.find_targets(p),[])
            image.chmod(0o755); target=launch.find_targets(p)[0]
            launch.start_target(target)
            self.assertEqual(popen.call_args.args[0],(str(image),))
            self.assertNotIn('shell',popen.call_args.kwargs)

    def test_cli_only_tools_have_no_assumed_desktop_launcher(self):
        for manager in ('pipx','npm global','Cargo'):
            self.assertEqual(launch.find_targets(pkg(manager,'example')),[])

if __name__=='__main__': unittest.main()
