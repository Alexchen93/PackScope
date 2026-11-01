"""Private per-session operation logs; never capture polkit passwords."""
from datetime import datetime
import os
from pathlib import Path
import uuid


class SessionLog:
    def __init__(self):
        base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local/state')
        directory = base / 'packscope' / 'logs'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        name = datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:10] + '.log'
        self.path = directory / name
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(self.path, flags, 0o600)
        self.stream = os.fdopen(fd, 'w', encoding='utf-8', buffering=1)

    def write(self, message):
        timestamp = datetime.now().astimezone().isoformat(timespec='seconds')
        for line in str(message).splitlines() or ['']:
            self.stream.write(f'[{timestamp}] {line}\n')
        self.stream.flush()

    def close(self):
        self.stream.close()
