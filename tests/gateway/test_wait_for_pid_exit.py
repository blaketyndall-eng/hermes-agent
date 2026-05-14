"""Tests for _wait_for_pid_exit_async and _wait_for_pid_exit_sync (W2-T21).

Verifies that the async variant yields to the event loop between polls
(does not block) and that the sync variant still works correctly.
"""
import asyncio
import time
import unittest
from unittest.mock import patch


class TestWaitForPidExitAsync(unittest.IsolatedAsyncioTestCase):
    async def test_wait_for_pid_exit_async_returns_when_pid_gone(self):
        """Returns True once _pid_exists reports False; does not block the loop."""
        from gateway.run import _wait_for_pid_exit_async

        call_count = 0

        def mock_pid_exists(pid):
            nonlocal call_count
            call_count += 1
            # True on first two calls, False (process gone) on third
            return call_count <= 2

        # Sentinel coroutine: if the event loop is not blocked, this tiny
        # sleep will complete while _wait_for_pid_exit_async is still
        # polling, proving the loop was not held hostage.
        sentinel_ran = {"value": False, "at": None}

        async def sentinel():
            await asyncio.sleep(0.01)
            sentinel_ran["value"] = True
            sentinel_ran["at"] = time.monotonic()

        start = time.monotonic()

        with patch("gateway.status._pid_exists", side_effect=mock_pid_exists):
            sentinel_task = asyncio.create_task(sentinel())
            result = await _wait_for_pid_exit_async(pid=12345, total_seconds=10.0, interval=0.05)
            await sentinel_task

        elapsed = time.monotonic() - start

        assert result is True, "Expected True when pid_exists returns False"
        assert sentinel_ran["value"], (
            "Sentinel coroutine did not run while _wait_for_pid_exit_async "
            "was polling — event loop appears blocked"
        )
        assert elapsed < 1.0, (
            f"Function took {elapsed:.2f}s — expected to return quickly once "
            "pid is gone, not block for the full timeout"
        )

    async def test_wait_for_pid_exit_async_returns_false_on_timeout(self):
        """Returns False if the process never exits within total_seconds."""
        from gateway.run import _wait_for_pid_exit_async

        with patch("gateway.status._pid_exists", return_value=True):
            result = await _wait_for_pid_exit_async(
                pid=99999, total_seconds=0.1, interval=0.03
            )

        assert result is False, "Expected False when process never exits"


class TestWaitForPidExitSync(unittest.TestCase):
    def test_wait_for_pid_exit_sync_still_works(self):
        """Sync variant returns True once _pid_exists reports False."""
        from gateway.run import _wait_for_pid_exit_sync

        call_count = 0

        def mock_pid_exists(pid):
            nonlocal call_count
            call_count += 1
            return call_count <= 2

        start = time.monotonic()
        with patch("gateway.status._pid_exists", side_effect=mock_pid_exists):
            result = _wait_for_pid_exit_sync(pid=12345, total_seconds=5.0, interval=0.05)
        elapsed = time.monotonic() - start

        assert result is True, "Expected True when _pid_exists returns False"
        assert elapsed < 1.0, (
            f"Sync variant took {elapsed:.2f}s — should return early, not run full timeout"
        )

    def test_wait_for_pid_exit_sync_returns_false_on_timeout(self):
        """Sync variant returns False if the process never exits."""
        from gateway.run import _wait_for_pid_exit_sync

        with patch("gateway.status._pid_exists", return_value=True):
            result = _wait_for_pid_exit_sync(
                pid=99999, total_seconds=0.1, interval=0.03
            )

        assert result is False, "Expected False when process never exits"


if __name__ == "__main__":
    unittest.main()
