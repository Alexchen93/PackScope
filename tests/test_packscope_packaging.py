import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class PackageBuildTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('dpkg-deb'),'需要 dpkg-deb')
    def test_deb_build_contains_launcher_and_desktop_integration(self):
        root=Path(__file__).resolve().parent
        if root.name=='tests': root=root.parent
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out'; extracted=Path(tmp)/'extracted'
            subprocess.run(['sh',str(root/'packaging/build-deb.sh'),str(out)],check=True,capture_output=True,text=True)
            package=out/'packscope_0.2.0~dev1_all.deb'
            self.assertTrue(package.is_file())
            self.assertEqual(subprocess.run(['dpkg-deb','-f',str(package),'Version'],check=True,capture_output=True,text=True).stdout.strip(),'0.2.0~dev1')
            subprocess.run(['dpkg-deb','-x',str(package),str(extracted)],check=True,capture_output=True,text=True)
            self.assertTrue((extracted/'usr/bin/packscope').is_file())
            self.assertTrue((extracted/'usr/lib/packscope/packscope/app.py').is_file())
            desktop=(extracted/'usr/share/applications/packscope.desktop').read_text()
            self.assertIn('Exec=packscope',desktop)
            installed_icon=extracted/'usr/share/icons/hicolor/scalable/apps/packscope.svg'
            self.assertTrue(installed_icon.is_file())
            self.assertEqual(installed_icon.read_bytes(),(root/'packscope/assets/packscope.svg').read_bytes())

if __name__=='__main__': unittest.main()
