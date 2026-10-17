"""Stage 11 observability unit tests — no SOS sends, no model training."""

from __future__ import annotations

import json
from pathlib import Path

from app.observability import JsonFormatter, phone_suffix, metrics
from app.services.audit_log import write_audit_event, purge_old_audit_files, _redact
from app.services.ai_alert_service import compute_fused_confidence
from app.config import settings


def test_phone_suffix():
    assert phone_suffix("+919876543210") == "3210"
    assert phone_suffix("") == "****"


def test_json_formatter_emits_json():
    import logging

    record = logging.LogRecord(
        name="t",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "rid-1"
    record.duration_ms = 12.5
    line = JsonFormatter().format(record)
    payload = json.loads(line)
    assert payload["message"] == "hello"
    assert payload["request_id"] == "rid-1"
    assert payload["duration_ms"] == 12.5


def test_metrics_snapshot():
    metrics.reset_for_tests()
    metrics.incr("http_requests_total")
    metrics.observe_ms("http_request", 10)
    metrics.observe_ms("http_request", 30)
    snap = metrics.snapshot()
    assert snap["counters"]["http_requests_total"] == 1
    assert snap["latency"]["http_request"]["count"] == 2
    assert snap["latency"]["http_request"]["p50_ms"] is not None


def test_audit_redacts_transcript_and_maps(tmp_path, monkeypatch):
    import app.services.audit_log as al

    monkeypatch.setattr(
        al,
        "settings",
        type(
            "S",
            (),
            {
                "AUDIT_LOG_DIR": str(tmp_path),
                "AUDIT_RETENTION_DAYS": 30,
                "ENVIRONMENT": "development",
                "AI_AUTO_SOS_ENABLED": False,
            },
        )(),
    )
    write_audit_event(
        "unit_test",
        detail={
            "transcript": "help me",
            "maps_url": "https://maps.example/1,2",
            "action": "confirm_30s",
            "phone": "+911111",
        },
    )
    files = list(Path(tmp_path).glob("audit_*.jsonl"))
    assert files
    row = json.loads(files[0].read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["ai_auto_sos_enabled"] is False
    assert row["detail"]["transcript"] == "[REDACTED]"
    assert row["detail"]["maps_url"] == "[REDACTED]"
    assert row["detail"]["phone"] == "[REDACTED]"
    assert row["detail"]["action"] == "confirm_30s"


def test_redact_helper_preserves_safe_keys():
    out = _redact({"action": "nothing", "audio_pcm": "xxxx", "score": 0.2})
    assert out["action"] == "nothing"
    assert out["audio_pcm"] == "[REDACTED]"
    assert out["score"] == 0.2


def test_confidence_records_metrics_without_phrase_in_audit(tmp_path, monkeypatch):
    metrics.reset_for_tests()
    import app.services.ai_alert_service as aas
    import app.services.audit_log as al

    monkeypatch.setattr(
        al,
        "settings",
        type(
            "S",
            (),
            {
                "AUDIT_LOG_DIR": str(tmp_path),
                "AUDIT_RETENTION_DAYS": 30,
                "ENVIRONMENT": "development",
                "AI_AUTO_SOS_ENABLED": False,
            },
        )(),
    )
    monkeypatch.setattr(aas, "settings", settings)

    result = compute_fused_confidence(
        audio_score=0.1,
        phrase_score=0.9,
        detected_phrase="help me please",
        fall_detected=False,
    )
    assert result["confirm_first"]["ai_auto_sos_enabled"] is False
    assert result["confirm_first"]["real_alert_allowed"] is False
    snap = metrics.snapshot()
    assert snap["counters"]["ai_confidence_requests_total"] >= 1
    assert "ai_confidence_fusion" in snap["latency"]

    text = Path(tmp_path).glob("audit_*.jsonl")
    content = next(text).read_text(encoding="utf-8")
    assert "help me please" not in content
    assert "ai_inference" in content


def test_ai_auto_sos_still_false():
    assert settings.AI_AUTO_SOS_ENABLED is False


def test_purge_noop_recent(tmp_path, monkeypatch):
    import app.services.audit_log as al

    monkeypatch.setattr(
        al,
        "settings",
        type(
            "S",
            (),
            {
                "AUDIT_LOG_DIR": str(tmp_path),
                "AUDIT_RETENTION_DAYS": 30,
                "ENVIRONMENT": "development",
                "AI_AUTO_SOS_ENABLED": False,
            },
        )(),
    )
    p = tmp_path / "audit_2099-01-01.jsonl"
    p.write_text("{}\n", encoding="utf-8")
    assert purge_old_audit_files() == 0
    assert p.exists()
