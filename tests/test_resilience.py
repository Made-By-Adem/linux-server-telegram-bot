"""Regression tests for callback/config resilience fixes."""

from pathlib import Path
from types import SimpleNamespace

from linux_server_bot.bot.callbacks import safe_answer_callback_query
from linux_server_bot.config import AppConfig, _ConfigReloadHandler


class _DummyBot:
    def __init__(self, exc: Exception | None = None):
        self.exc = exc

    def answer_callback_query(self, call_id, text=None):
        if self.exc:
            raise self.exc
        return True


def test_safe_answer_callback_query_handles_expired_callback():
    bot = _DummyBot(Exception("Bad Request: query is too old and response timeout expired or query ID is invalid"))
    ok = safe_answer_callback_query(bot, "123", "Fetching status...")
    assert ok is False


def test_config_reload_handler_triggers_on_moved_to_target(tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("telegram: {}\n")

    handler = _ConfigReloadHandler(Path(cfg), AppConfig())
    called = {"value": False}

    def fake_schedule_reload():
        called["value"] = True

    handler._schedule_reload = fake_schedule_reload  # type: ignore[attr-defined]

    event = SimpleNamespace(src_path=str(tmp_path / "tmp.yaml"), dest_path=str(cfg))
    handler.on_moved(event)

    assert called["value"] is True
