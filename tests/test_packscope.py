import unittest
from unittest.mock import patch
from packscope.inventory import Package, ScanResult, scan_all

class InventoryTests(unittest.TestCase):
    def test_failure_is_reported_separately_from_empty_result(self):
        with (patch('packscope.inventory.debian', return_value=ScanResult('APT / dpkg', [], 'ok')),
             patch('packscope.inventory.snap', side_effect=PermissionError('denied')),
             patch('packscope.inventory.flatpak', return_value=ScanResult('Flatpak', [], 'unavailable')),
             patch('packscope.inventory.appimage', return_value=ScanResult('AppImage', [], 'ok')),
             patch('packscope.inventory.pipx', return_value=ScanResult('pipx', [], 'unavailable')),
             patch('packscope.inventory.npm', return_value=ScanResult('npm global', [], 'unavailable')),
             patch('packscope.inventory.cargo', return_value=ScanResult('Cargo', [], 'unavailable'))):
            results = scan_all()
        self.assertEqual([r.status for r in results], ['ok', 'error', 'unavailable', 'ok', 'unavailable', 'unavailable', 'unavailable'])
        self.assertIn('denied', results[1].detail)

    def test_same_name_from_different_sources_stays_distinct(self):
        records = [Package('Example', 'example', '1', 'Snap'), Package('Example', 'example', '1', 'Flatpak')]
        self.assertNotEqual(records[0], records[1])

if __name__ == '__main__': unittest.main()
