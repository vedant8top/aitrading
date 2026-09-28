import pytest
import os
from unittest.mock import patch, MagicMock
from src.audit.readiness_audit import ReadinessAudit

def test_audit_exchange_layer_missing_file(tmp_path):
    audit = ReadinessAudit()
    with patch("src.audit.readiness_audit.PROJECT_ROOT", tmp_path):
        audit.audit_exchange_layer()
        assert len(audit.results) == 1
        assert audit.results[0]["passed"] is False
        assert audit.results[0]["detail"] == ".env file not found"

def test_audit_exchange_layer_empty_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("")
    audit = ReadinessAudit()
    with patch("src.audit.readiness_audit.PROJECT_ROOT", tmp_path):
        audit.audit_exchange_layer()
        assert len(audit.results) == 1
        assert audit.results[0]["passed"] is False
        assert "Binance credentials missing or are placeholders" in audit.results[0]["detail"]

def test_audit_exchange_layer_placeholders(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("BINANCE_API_KEY=PASTE_YOUR_API_KEY_HERE\nBINANCE_SECRET_KEY=PASTE_YOUR_SECRET_KEY_HERE")
    audit = ReadinessAudit()
    with patch("src.audit.readiness_audit.PROJECT_ROOT", tmp_path):
        audit.audit_exchange_layer()
        assert len(audit.results) == 1
        assert audit.results[0]["passed"] is False
        assert "Binance credentials missing or are placeholders" in audit.results[0]["detail"]

def test_audit_exchange_layer_valid(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('BINANCE_API_KEY="valid_key"\nBINANCE_SECRET_KEY="valid_secret"')
    audit = ReadinessAudit()
    with patch("src.audit.readiness_audit.PROJECT_ROOT", tmp_path):
        audit.audit_exchange_layer()
        assert len(audit.results) == 1
        assert audit.results[0]["passed"] is True
        assert "Binance credentials configured" in audit.results[0]["detail"]
