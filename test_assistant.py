"""Offline behavior tests; no connected accounts or paid API calls."""

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from pydantic import ValidationError

from briefing import BriefingData, Event, Task, build_context
from main import Settings, ai_briefing, create_app

ZONE = ZoneInfo("America/New_York")
NOW = datetime(2026, 10, 16, 14, 0, tzinfo=timezone.utc)  # 10 AM in New York
TOKEN = "offline-test-token-" + "a" * 32


def fixture():
    return BriefingData(
        is_demo=True, updated_at=NOW,
        events=[Event(title="Already finished", start=NOW - timedelta(hours=2),
                      end=NOW - timedelta(hours=1)),
                Event(title="Upcoming class", start=NOW + timedelta(minutes=50),
                      end=NOW + timedelta(hours=2))],
        tasks=[Task(title="Completed task", due=NOW, estimated_minutes=5, completed=True),
               Task(title="Overdue analysis", due=NOW - timedelta(days=1), estimated_minutes=45),
               Task(title="Short follow-up", due=NOW + timedelta(hours=2), estimated_minutes=10)],
    )


class ScheduleTests(unittest.TestCase):
    def test_filters_completed_items_and_caps_window_before_class(self):
        context = build_context(fixture(), NOW, ZONE, 60)
        self.assertEqual([e["title"] for e in context["events"]], ["Upcoming class"])
        self.assertNotIn("Completed task", [t["title"] for t in context["tasks"]])
        self.assertEqual(context["tasks"][0]["due"], "overdue")
        self.assertEqual(context["available_minutes"], 40)
        self.assertEqual(context["suggested_task"]["title"], "Short follow-up")

    def test_ongoing_overnight_shift_blocks_task_suggestion(self):
        now = datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc)
        data = BriefingData(updated_at=now,
            events=[Event(title="Overnight shift", start=now - timedelta(hours=4),
                          end=now + timedelta(hours=2))], tasks=fixture().tasks)
        context = build_context(data, now, ZONE, 30)
        self.assertEqual(context["active_event"], "Overnight shift")
        self.assertEqual(context["available_minutes"], 0)
        self.assertIsNone(context["suggested_task"])

    def test_local_midnight_includes_local_today_and_excludes_tomorrow(self):
        now = datetime(2026, 10, 17, 3, 30, tzinfo=timezone.utc)  # Oct 16, 11:30 PM
        data = BriefingData(updated_at=now, events=[
            Event(title="Tonight", start=now + timedelta(minutes=10), end=now + timedelta(minutes=20)),
            Event(title="Tomorrow", start=now + timedelta(minutes=40), end=now + timedelta(hours=1)),
        ])
        context = build_context(data, now, ZONE, 30)
        self.assertEqual([event["title"] for event in context["events"]], ["Tonight"])

    def test_no_task_fits_short_window(self):
        context = build_context(fixture(), NOW, ZONE, 5)
        self.assertIsNone(context["suggested_task"])

    def test_naive_timestamps_and_backwards_events_are_rejected(self):
        for values in [dict(start=datetime(2026, 10, 16), end=datetime(2026, 10, 17)),
                       dict(start=NOW, end=NOW - timedelta(hours=1))]:
            with self.assertRaises(ValidationError):
                Event(title="Invalid", **values)


class EndpointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "data.json"
        self.path.write_text(fixture().model_dump_json(), encoding="utf-8")
        self.settings = Settings(token=TOKEN, data_path=self.path)
        self.headers = {"Authorization": f"Bearer {TOKEN}"}
        self.client = TestClient(create_app(self.settings))
        self.addCleanup(self.client.close)

    def test_health_is_public_but_briefing_requires_token(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
        self.assertEqual(self.client.get("/briefing").status_code, 401)
        self.assertEqual(self.client.get("/briefing", headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.client.get("/briefing", headers={"Authorization": "Bearer \u00e9".encode("utf-8")}).status_code, 401)

    def test_missing_server_token_never_makes_briefing_public(self):
        with TestClient(create_app(replace(self.settings, token=""))) as client:
            self.assertEqual(client.get("/briefing", headers=self.headers).status_code, 503)

    def test_demo_and_disconnected_sources_are_explicit(self):
        response = self.client.get("/briefing", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        result = response.json()
        self.assertTrue(result["speech"].startswith("Demo briefing."))
        self.assertEqual(result["engine"], "template")
        self.assertEqual(result["sources"]["email"], "not_connected")
        self.assertIn("Email and stock updates are not connected", result["speech"])

    def test_bad_file_is_an_explicit_error(self):
        self.path.write_text('{"is_demo":false}', encoding="utf-8")
        response = self.client.get("/briefing", headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.path), response.text)

    def test_unknown_mode_or_invalid_window_is_rejected(self):
        for query in ("mode=unknown", "available_minutes=0", "available_minutes=999"):
            self.assertEqual(self.client.get("/briefing?" + query, headers=self.headers).status_code, 422)

    def test_old_data_warning_is_spoken(self):
        data = fixture().model_copy(update={"updated_at": datetime.now(timezone.utc) - timedelta(days=3)})
        self.path.write_text(data.model_dump_json(), encoding="utf-8")
        speech = self.client.get("/briefing", headers=self.headers).json()["speech"]
        self.assertIn("more than 36 hours old", speech)

    def test_ai_failure_returns_labeled_fallback(self):
        settings = replace(self.settings, use_ai=True, api_key="offline-key", model="offline-model")
        with patch("main.ai_briefing", side_effect=TimeoutError), TestClient(create_app(settings)) as client:
            result = client.get("/briefing", headers=self.headers).json()
        self.assertEqual(result["ai_status"], "unavailable")
        self.assertEqual(result["engine"], "template")
        self.assertIn("AI summarization is unavailable", result["speech"])

    def test_missing_ai_credentials_returns_labeled_fallback(self):
        with TestClient(create_app(replace(self.settings, use_ai=True))) as client:
            result = client.get("/briefing", headers=self.headers).json()
        self.assertEqual(result["ai_status"], "unavailable")

    def test_ai_summary_cannot_remove_demo_or_source_labels(self):
        settings = replace(self.settings, use_ai=True, api_key="offline-key", model="offline-model")
        with patch("main.ai_briefing", return_value="Your summary."), TestClient(create_app(settings)) as client:
            result = client.get("/briefing", headers=self.headers).json()
        self.assertTrue(result["speech"].startswith("Demo briefing."))
        self.assertIn("Your summary.", result["speech"])
        self.assertEqual(result["engine"], "openai")

    def test_sdk_boundary_sends_only_provided_facts_and_does_not_retry(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(status="completed", output_text="  Update.  ")
        settings = replace(self.settings, use_ai=True, api_key="offline-key", model="offline-model")
        with patch("openai.OpenAI", return_value=client) as factory:
            self.assertEqual(ai_briefing({"events": []}, "morning", settings), "Update.")
        factory.assert_called_once_with(api_key="offline-key", timeout=12.0, max_retries=0)
        payload = client.responses.create.call_args.kwargs
        self.assertFalse(payload["store"])
        self.assertEqual(json.loads(payload["input"])["facts"], {"events": []})
        client.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
