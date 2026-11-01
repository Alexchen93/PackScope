"""Qt background tasks for inventory queries and package operations."""
import shlex

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from packscope import actions
from packscope.inventory import ScanResult


class Worker(QObject):
    done = pyqtSignal(object)

    def __init__(self, scan):
        super().__init__()
        self.scan = scan

    def run(self):
        try:
            results = self.scan()
        except Exception as exc:
            results = [ScanResult('掃描', [], 'error', str(exc) or type(exc).__name__)]
        self.done.emit(results)


class Task(QThread):
    result_ready = pyqtSignal(object, object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.result_ready.emit(self.fn(), None)
        except Exception as exc:
            self.result_ready.emit(None, str(exc) or type(exc).__name__)


class OperationTask(QThread):
    output = pyqtSignal(str)
    progress = pyqtSignal(int)
    result_ready = pyqtSignal(object, object)

    def __init__(self, operation, parent=None):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            if self.operation.argv:
                self.output.emit('$ ' + shlex.join(self.operation.argv))
            else:
                self.output.emit('正在複製 AppImage 並建立桌面捷徑。')
            result = actions.execute(self.operation, self.output.emit, self.progress.emit)
            self.result_ready.emit(result, None)
        except Exception as exc:
            self.result_ready.emit(None, str(exc) or type(exc).__name__)


class BatchOperationTask(QThread):
    output = pyqtSignal(str)
    progress = pyqtSignal(int)
    result_ready = pyqtSignal(int, object)

    def __init__(self, operations, parent=None):
        super().__init__(parent)
        self.operations = operations

    def run(self):
        failures = []
        succeeded = 0
        total = len(self.operations)
        for index, operation in enumerate(self.operations):
            self.output.emit(f'[{index + 1}/{total}] {operation.package.name}（{operation.package.manager}）')
            self.output.emit('$ ' + shlex.join(operation.argv))
            try:
                actions.execute(operation, self.output.emit,
                                lambda value, i=index: self.progress.emit(min(99, (i * 100 + value) // total)))
                succeeded += 1
                self.output.emit('已完成：' + operation.package.name)
            except Exception as exc:
                message = str(exc) or type(exc).__name__
                failures.append((operation.package.name, message))
                self.output.emit('未完成：' + operation.package.name + ' — ' + message.split('\n\n', 1)[0])
            self.progress.emit(min(99, ((index + 1) * 100) // total))
        self.result_ready.emit(succeeded, failures)
