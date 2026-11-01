import unittest
import threading
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
             patch('packscope.inventory.cargo', return_value=ScanResult('Cargo', [], 'unavailable')),
             self.assertLogs('packscope', level='ERROR')):
            results = scan_all()
        self.assertEqual([r.status for r in results], ['ok', 'error', 'unavailable', 'ok', 'unavailable', 'unavailable', 'unavailable'])
        self.assertIn('denied', results[1].detail)

    def test_same_name_from_different_sources_stays_distinct(self):
        records = [Package('Example', 'example', '1', 'Snap'), Package('Example', 'example', '1', 'Flatpak')]
        self.assertNotEqual(records[0], records[1])

    def test_scans_sources_concurrently_and_preserves_order(self):
        barrier = threading.Barrier(2)
        def delayed(name):
            barrier.wait(timeout=2)
            return ScanResult(name, [], 'ok')
        with (patch('packscope.inventory.debian', side_effect=lambda: delayed('APT / dpkg')),
              patch('packscope.inventory.snap', side_effect=lambda: delayed('Snap')),
              patch('packscope.inventory.flatpak', return_value=ScanResult('Flatpak', [], 'ok')),
              patch('packscope.inventory.appimage', return_value=ScanResult('AppImage', [], 'ok')),
              patch('packscope.inventory.pipx', return_value=ScanResult('pipx', [], 'ok')),
              patch('packscope.inventory.npm', return_value=ScanResult('npm global', [], 'ok')),
              patch('packscope.inventory.cargo', return_value=ScanResult('Cargo', [], 'ok'))):
            results = scan_all()
        self.assertEqual([r.manager for r in results[:2]], ['APT / dpkg', 'Snap'])
        self.assertTrue(all(r.status == 'ok' for r in results))

if __name__ == '__main__': unittest.main()
