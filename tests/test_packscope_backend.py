import csv
import gzip
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from packscope import backend
from packscope.inventory import Package


def package(name='example', manager='APT / dpkg'):
    return Package(name, name, '1', manager)


class BackendTests(unittest.TestCase):
    @patch('packscope.backend.command')
    def test_update_checks_report_each_source_and_failures(self, command):
        command.side_effect = [
            subprocess.CompletedProcess([], 0, 'Inst example [1] (2 repo)\n', ''),
            subprocess.CalledProcessError(1, 'flatpak'),
            subprocess.CompletedProcess([], 0, '', ''),
            subprocess.CompletedProcess([], 0, 'Name Version Rev Size Publisher Notes\nexample 2 3 4 pub -\n', ''),
        ]
        results = backend.check_updates()
        self.assertIn('example  1 → 2', results[0][2])
        self.assertIsNotNone(results[1][3])
        self.assertEqual(len(results[3][2]), 1)
        self.assertIn('尚未檢查', results[4][1])

    def test_export_is_filtered_and_csv_formulas_are_neutralized(self):
        rows = [package('=unsafe'), package('normal')]
        with tempfile.TemporaryDirectory() as tmp:
            csvfile = Path(tmp) / 'out.csv'
            jsonfile = Path(tmp) / 'out.json'
            backend.export_inventory(csvfile, rows, 'csv')
            with csvfile.open(encoding='utf-8', newline='') as source:
                result = list(csv.DictReader(source))
            self.assertEqual(result[0]['name'], "'=unsafe")
            backend.export_inventory(jsonfile, rows[:1], 'json')
            self.assertEqual(len(json.loads(jsonfile.read_text())['packages']), 1)
            markdown = Path(tmp) / 'out.md'
            backend.export_inventory(markdown, [package('a|b')], 'md')
            self.assertIn('a\\|b', markdown.read_text())

    def test_failed_export_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'old.json'
            dest.write_text('existing data')
            with patch('packscope.backend.os.replace', side_effect=OSError('failure')):
                with self.assertRaises(OSError):
                    backend.export_inventory(dest, [package()], 'json')
            self.assertEqual(dest.read_text(), 'existing data')
            self.assertEqual([p.name for p in Path(tmp).iterdir()], ['old.json'])

    @patch('packscope.backend.command')
    def test_flatpak_ref_and_scope_are_preserved(self, command):
        command.return_value = subprocess.CompletedProcess([], 0, stdout='metadata', stderr='')
        p = Package('Example', 'org.example.App/x86_64/stable', '1', 'Flatpak', '使用者')
        self.assertIn('metadata', backend.details(p))
        self.assertEqual(command.call_args.args[0], ['flatpak', 'info', '--user', p.ident])

    def test_history_matches_package_and_arch_without_inferring_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'dpkg.log').write_text(
                '2026-01-02 10:00:00 upgrade example:amd64 1 2\n'
                '2026-01-03 10:00:00 remove example:i386 2 <none>\n'
                '2026-01-04 10:00:00 install example-extra:amd64 <none> 1\n')
            with gzip.open(Path(tmp, 'dpkg.log.2.gz'), 'wt') as log:
                log.write('2026-01-01 10:00:00 install example:amd64 <none> 1\n')
            result=backend.package_history(package('example:amd64'), tmp)
        self.assertIn('upgrade example:amd64', result)
        self.assertIn('install example:amd64', result)
        self.assertNotIn('example-extra', result)
        self.assertNotIn('example:i386', result)
        self.assertIn('無法單獨證明', result)


if __name__ == '__main__': unittest.main()
