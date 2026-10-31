import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from packscope import inventory


class DeveloperInventoryTests(unittest.TestCase):
    def test_pipx_reads_metadata_without_executing_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'venvs'/'example'
            folder.mkdir(parents=True)
            (folder/'pipx_metadata.json').write_text(json.dumps({'main_package': {'package':'example', 'package_version':'1.2'}}))
            with patch.dict(os.environ, {'PIPX_HOME':tmp}), patch('packscope.inventory.shutil.which',return_value='/usr/bin/pipx'):
                result=inventory.pipx()
            self.assertEqual([(p.ident,p.version) for p in result.packages], [('example','1.2')])

    def test_cargo_reads_registry_without_creating_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            metadata=Path(tmp)/'.crates.toml'
            metadata.write_text('[v1]\n"example 1.2 (registry+https://example.invalid)" = ["example"]\n')
            with patch.dict(os.environ, {'CARGO_HOME':tmp}), patch('packscope.inventory.shutil.which',return_value='/usr/bin/cargo'):
                result=inventory.cargo()
            self.assertEqual([(p.ident,p.version) for p in result.packages], [('example','1.2')])
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ['.crates.toml'])

    @patch('packscope.inventory.command')
    @patch('packscope.inventory.shutil.which',return_value='/usr/bin/npm')
    def test_npm_parses_global_packages_and_uses_temporary_cache(self, which, command):
        command.return_value=subprocess.CompletedProcess([],0,json.dumps({'dependencies':{'@test/tool':{'version':'2.0'}}}), '')
        result=inventory.npm()
        self.assertEqual([(p.ident,p.version) for p in result.packages], [('@test/tool','2.0')])
        self.assertIn('--cache',command.call_args.args[0])


if __name__ == '__main__': unittest.main()
