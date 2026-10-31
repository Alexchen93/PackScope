"""Regression checks for the fixed-edge, resizable table header."""
import os
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt5.QtWidgets import QApplication, QHeaderView, QTableView
from packscope.app import FittedHeader, Model


class TableLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.table = QTableView()
        self.model = Model()
        self.table.setModel(self.model)
        self.header = FittedHeader(self.table)
        self.table.setHorizontalHeader(self.header)
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setMinimumSectionSize(55)
        self.header.setStretchLastSection(True)
        for i, width in enumerate((230, 115, 165, 75)):
            self.table.setColumnWidth(i, width)
        self.header.enable_fitting()
        self.table.resize(850, 500)
        self.table.show()
        self.flush()

    def flush(self):
        for _ in range(5):
            self.app.processEvents()

    def assert_fits(self):
        self.flush()
        self.assertLessEqual(abs(self.header.length() - self.table.viewport().width()), 1)
        self.assertEqual(self.table.horizontalScrollBar().maximum(), 0)

    def test_divider_moves_neighbour_and_stays_within_edges(self):
        first, second = self.header.sectionSize(0), self.header.sectionSize(1)
        self.header.resizeSection(0, first + 30)
        self.assertEqual(self.header.sectionSize(0), first + 30)
        self.assertEqual(self.header.sectionSize(1), second - 30)
        self.header.resizeSection(0, 5000)
        self.assertEqual(self.header.sectionSize(1), self.header.minimumSectionSize())
        self.assert_fits()

    def test_window_resize_stays_fitted(self):
        self.table.resize(400, 500)
        self.assert_fits()
        self.table.resize(1100, 500)
        self.assert_fits()

    def tearDown(self):
        self.table.close()
        self.flush()


if __name__ == '__main__':
    unittest.main()
