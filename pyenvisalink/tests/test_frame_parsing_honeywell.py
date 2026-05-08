"""Regression tests for data_received buffering across TCP read boundaries.

Without buffering, a frame split across two TCP recv() calls is processed as
two malformed pieces and logged as "Unrecognized data recieved". These tests
feed byte chunks through HoneywellClient.data_received and verify each
complete frame reaches the parser exactly once.
"""

import unittest
from unittest.mock import MagicMock

from pyenvisalink import AlarmState
from pyenvisalink.honeywell_client import HoneywellClient


class _TestClient(HoneywellClient):
    """HoneywellClient with the asyncio side of __init__ skipped, plus a
    capture of every line that reaches the parser for assertion."""

    def __init__(self):
        panel = MagicMock()
        panel.alarm_state = AlarmState.get_initial_alarm_state(64, 8)
        self._loggedin = True
        self._alarmPanel = panel
        self._transport = None
        self._shutdown = False
        self._cachedCode = None
        self._reconnect_task = None
        self._readBuffer = ''
        self.parsed = []

    def parseHandler(self, line):
        self.parsed.append(line)
        return super().parseHandler(line)


class TestDataReceivedBuffering(unittest.TestCase):
    def setUp(self):
        self.client = _TestClient()

    def test_complete_frame_in_one_chunk(self):
        self.client.data_received(b"%01,02000004000000000000000000000000$\r\n")
        self.assertEqual(self.client.parsed, ["%01,02000004000000000000000000000000$"])

    def test_two_frames_in_one_chunk(self):
        self.client.data_received(
            b"%01,02000004000000000000000000000000$\r\n"
            b"%00,01,1C08,08,00,****DISARMED****  Ready to Arm  $\r\n"
        )
        self.assertEqual(self.client.parsed, [
            "%01,02000004000000000000000000000000$",
            "%00,01,1C08,08,00,****DISARMED****  Ready to Arm  $",
        ])

    def test_frame_split_mid_payload(self):
        """The reproducer for the bug: TCP delivers half a frame, then the rest."""
        full = b"%00,01,0008,30,00,FAULT 30                        $\r\n"
        first, second = full[:26], full[26:]
        self.client.data_received(first)
        self.assertEqual(self.client.parsed, [])  # truncated line must not reach the parser
        self.client.data_received(second)
        self.assertEqual(self.client.parsed, [
            "%00,01,0008,30,00,FAULT 30                        $",
        ])

    def test_frame_split_at_terminator(self):
        """The CRLF itself is split between two recv() calls."""
        self.client.data_received(b"%02,01000000$\r")
        self.assertEqual(self.client.parsed, [])
        self.client.data_received(b"\n")
        self.assertEqual(self.client.parsed, ["%02,01000000$"])

    def test_split_inside_middle_frame(self):
        self.client.data_received(
            b"%01,02000004000000000000000000000000$\r\n"
            b"%00,01,0008,05,00,FAULT"
        )
        self.assertEqual(self.client.parsed, ["%01,02000004000000000000000000000000$"])
        self.client.data_received(
            b" 05                        $\r\n"
            b"%02,03000000$\r\n"
        )
        self.assertEqual(self.client.parsed, [
            "%01,02000004000000000000000000000000$",
            "%00,01,0008,05,00,FAULT 05                        $",
            "%02,03000000$",
        ])

    def test_empty_chunk_is_a_noop(self):
        self.client.data_received(b"")
        self.assertEqual(self.client.parsed, [])
        self.assertEqual(self.client._readBuffer, "")

    def test_login_prompt_is_delivered_when_terminator_arrives(self):
        """Pre-login the EVL sends 'Login:\\r\\n'; buffer must release it."""
        self.client._loggedin = False
        self.client.data_received(b"Login:")
        self.assertEqual(self.client.parsed, [])
        self.client.data_received(b"\r\n")
        self.assertEqual(self.client.parsed, ["Login:"])

    def test_disconnect_clears_partial_buffer(self):
        """A reconnect must not prepend stale bytes from the previous session."""
        partial = b"%00,01,0008,30,00,partial-no-CRLF"
        self.client.data_received(partial)
        self.assertEqual(self.client._readBuffer, partial.decode())
        self.client.disconnect()
        self.assertEqual(self.client._readBuffer, "")
        # Fresh frame after reconnect parses cleanly without prefix corruption.
        self.client.data_received(b"%01,02000004000000000000000000000000$\r\n")
        self.assertEqual(self.client.parsed, ["%01,02000004000000000000000000000000$"])


if __name__ == "__main__":
    unittest.main()
