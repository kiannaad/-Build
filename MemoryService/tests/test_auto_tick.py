import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import auto_tick  # noqa: E402


class AutoTickTest(unittest.TestCase):
    def test_tick_once_calls_ingest_and_digest(self):
        with mock.patch.object(auto_tick.session_tail, "run",
                               return_value={"files": 2, "new_events": 5}) as run, \
             mock.patch.object(auto_tick.db, "init_db") as init_db, \
             mock.patch.object(auto_tick.digest, "generate") as gen:
            init_db.return_value = mock.MagicMock()
            result = auto_tick.tick_once()
        run.assert_called_once()
        gen.assert_called_once()
        self.assertEqual(result["ingest"]["new_events"], 5)
        self.assertRegex(result["digest_day"], r"^\d{4}-\d{2}-\d{2}$")

    def test_start_can_be_disabled(self):
        with mock.patch.dict(os.environ, {"DFY_MEMORY_AUTO_TICK": "0"}):
            self.assertIsNone(auto_tick.start())


if __name__ == "__main__":
    unittest.main(verbosity=2)
