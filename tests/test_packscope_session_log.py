import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from packscope.session_log import SessionLog


class SessionLogTests(unittest.TestCase):
    def test_sessions_are_separate_private_and_flushed(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'XDG_STATE_HOME': tmp}):
            first=SessionLog(); second=SessionLog()
            try:
                first.write('開始更新\n工具輸出')
                self.assertNotEqual(first.path,second.path)
                self.assertEqual(stat.S_IMODE(first.path.stat().st_mode),0o600)
                text=first.path.read_text(encoding='utf-8')
                self.assertIn('開始更新',text)
                self.assertIn('工具輸出',text)
                self.assertNotIn('開始更新',second.path.read_text(encoding='utf-8'))
            finally:
                first.close(); second.close()
