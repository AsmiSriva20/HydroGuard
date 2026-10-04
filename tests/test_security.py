"""
Tests for app/core/security.py -- the admin API key dependency added to
fix the missing-auth issue on device-mutating endpoints.

These call the dependency function directly rather than going through a
FastAPI TestClient + full app lifespan (which would need a live MongoDB
and MQTT broker to start up). That mirrors how the rest of this test
suite already tests service-layer functions directly.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import require_admin_api_key


def _settings(**overrides) -> Settings:
    defaults = {
        "app_env": "production",
        "admin_api_key": "correct-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestRequireAdminApiKey:
    def test_valid_key_is_accepted(self):
        # Should not raise.
        require_admin_api_key(
            provided_key="correct-key",
            settings=_settings(),
        )

    def test_missing_key_header_is_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            require_admin_api_key(
                provided_key=None,
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401

    def test_wrong_key_is_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            require_admin_api_key(
                provided_key="wrong-key",
                settings=_settings(),
            )
        assert exc_info.value.status_code == 401

    def test_unconfigured_key_in_production_is_rejected(self):
        """
        An empty ADMIN_API_KEY outside development must fail loudly
        (503) rather than silently accepting every request -- this is
        exactly the "looks protected, isn't actually enforced" gap the
        old unused jwt_secret setting had.
        """
        with pytest.raises(HTTPException) as exc_info:
            require_admin_api_key(
                provided_key=None,
                settings=_settings(app_env="production", admin_api_key=""),
            )
        assert exc_info.value.status_code == 503

    def test_unconfigured_key_in_development_is_allowed(self):
        # Should not raise: local dev works with zero setup.
        require_admin_api_key(
            provided_key=None,
            settings=_settings(app_env="development", admin_api_key=""),
        )

    def test_development_with_configured_key_still_enforces_it(self):
        """
        If a developer DOES set an admin key locally, it should still be
        checked -- development mode only relaxes the "no key configured"
        case, it doesn't disable the check outright.
        """
        with pytest.raises(HTTPException) as exc_info:
            require_admin_api_key(
                provided_key="wrong-key",
                settings=_settings(app_env="development", admin_api_key="correct-key"),
            )
        assert exc_info.value.status_code == 401
