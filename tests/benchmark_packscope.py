"""Optional read-only scan/filter benchmark, not a pass/fail performance test."""
import os
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PyQt5.QtWidgets import QApplication

from packscope import inventory
from packscope.app import Filter, Model


def main():
    app = QApplication.instance() or QApplication([])
    for name in ('debian', 'snap', 'flatpak', 'appimage', 'pipx', 'npm', 'cargo'):
        start = time.perf_counter()
        try:
            result = getattr(inventory, name)()
            print(f'{name}: {time.perf_counter() - start:.3f}s, {result.status}, {len(result.packages)} entries')
        except Exception as exc:
            print(f'{name}: {time.perf_counter() - start:.3f}s, {type(exc).__name__}: {exc}')
    start = time.perf_counter()
    inventory.scan_all()
    print(f'parallel scan: {time.perf_counter() - start:.3f}s')
    model = Model()
    model.replace([inventory.Package(f'Application {i}', f'package-{i}', '1', 'APT / dpkg',
                                     description='test package description', is_application=True)
                   for i in range(20000)])
    proxy = Filter()
    proxy.setSourceModel(model)
    for query in ('app', 'package-199', 'not-found'):
        start = time.perf_counter()
        proxy.set_query(query)
        count = proxy.rowCount()
        print(f'filter {query}: {time.perf_counter() - start:.3f}s, {count} entries')
    return app


if __name__ == '__main__':
    main()
