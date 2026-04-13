"""Tests for the shared logs action module."""

from linux_server_bot.config import config
from linux_server_bot.shared.actions.logs import list_available_logs, read_log_tail


class TestListAvailableLogs:
    def test_returns_empty_when_no_logfiles_configured(self):
        original = config.logfiles[:]
        config.logfiles = []
        try:
            assert list_available_logs() == []
        finally:
            config.logfiles = original

    def test_resolves_real_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        log_file.write_text("line1\nline2\n")
        original = config.logfiles[:]
        config.logfiles = [str(log_file)]
        try:
            entries = list_available_logs()
            assert len(entries) == 1
            assert entries[0]["name"] == "test.log"
            assert entries[0]["index"] == 0
            assert entries[0]["size_bytes"] > 0
        finally:
            config.logfiles = original


class TestReadLogTail:
    def test_read_tail_of_file(self, tmp_path):
        log_file = tmp_path / "test.log"
        lines = [f"line {i}\n" for i in range(100)]
        log_file.write_text("".join(lines))
        original = config.logfiles[:]
        config.logfiles = [str(log_file)]
        try:
            result = read_log_tail(0, tail=5)
            assert result["success"] is True
            assert result["lines_returned"] == 5
            assert result["total_lines"] == 100
            assert "line 99" in result["content"]
        finally:
            config.logfiles = original

    def test_invalid_index(self):
        original = config.logfiles[:]
        config.logfiles = []
        try:
            result = read_log_tail(999)
            assert result["success"] is False
            assert "Invalid log index" in result["error"]
        finally:
            config.logfiles = original
