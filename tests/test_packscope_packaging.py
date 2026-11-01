import importlib.util
import shutil
import sys
from zipfile import ZipFile
import subprocess
import tempfile
import unittest
from pathlib import Path

from packscope import __version__


class PackageBuildTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('dpkg-deb'),'需要 dpkg-deb')
    def test_deb_build_contains_launcher_and_desktop_integration(self):
        root=Path(__file__).resolve().parent
        if root.name=='tests': root=root.parent
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out'; extracted=Path(tmp)/'extracted'
            subprocess.run(['sh',str(root/'packaging/build-deb.sh'),str(out)],check=True,capture_output=True,text=True)
            package=out/f'packscope_{__version__.replace(".dev", "~dev")}_all.deb'
            self.assertTrue(package.is_file())
            self.assertEqual(subprocess.run(['dpkg-deb','-f',str(package),'Version'],check=True,capture_output=True,text=True).stdout.strip(),__version__.replace('.dev','~dev'))
            subprocess.run(['dpkg-deb','-x',str(package),str(extracted)],check=True,capture_output=True,text=True)
            self.assertTrue((extracted/'usr/bin/packscope').is_file())
            self.assertTrue((extracted/'usr/lib/packscope/packscope/app.py').is_file())
            desktop=(extracted/'usr/share/applications/packscope.desktop').read_text()
            self.assertIn('Exec=packscope %f',desktop)
            for mime in ('application/vnd.debian.binary-package', 'application/vnd.snap',
                         'application/vnd.flatpak', 'application/vnd.flatpak.ref',
                         'application/vnd.appimage'):
                self.assertIn(mime+';',desktop)
            installed_icon=extracted/'usr/share/icons/hicolor/scalable/apps/packscope.svg'
            self.assertTrue(installed_icon.is_file())
            self.assertEqual(installed_icon.read_bytes(),(root/'packscope/assets/packscope.svg').read_bytes())

    @unittest.skipUnless(importlib.util.find_spec('pip'), '需要 pip 建置 wheel')
    def test_wheel_identifies_packscope_and_includes_ui_assets(self):
        root=Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps',
                            '--no-build-isolation', '-w', tmp, str(root)],
                           check=True, capture_output=True, text=True)
            wheels=list(Path(tmp).glob('packscope-*.whl'))
            self.assertEqual(len(wheels),1)
            with ZipFile(wheels[0]) as wheel:
                names=wheel.namelist()
                metadata=wheel.read(next(name for name in names if name.endswith('.dist-info/METADATA'))).decode()
                entry_points=wheel.read(next(name for name in names if name.endswith('.dist-info/entry_points.txt'))).decode()
                self.assertIn('Name: packscope\n',metadata)
                self.assertIn('Version: '+__version__+'\n',metadata)
                self.assertIn('packscope = packscope.app:main',entry_points)
                self.assertNotIn('bauh =',entry_points)
                self.assertIn('packscope/assets/packscope.svg',names)
                self.assertIn('packscope/icons/chevron-dark.svg',names)


if __name__=='__main__': unittest.main()
