from types import SimpleNamespace

from api.core.bookmaker_freeze import (
    BOOKMAKER_FREEZE_UNIBET_ENV,
    filter_frozen_bookmaker_codes,
    is_bookmaker_frozen,
    is_unibet_frozen,
)
from api.services.subscription_service import SubscriptionService


def test_unibet_is_frozen_by_default(monkeypatch):
    monkeypatch.delenv(BOOKMAKER_FREEZE_UNIBET_ENV, raising=False)
    assert is_unibet_frozen() is True
    assert is_bookmaker_frozen("unibet") is True


def test_unibet_freeze_flag_can_be_disabled(monkeypatch):
    monkeypatch.setenv(BOOKMAKER_FREEZE_UNIBET_ENV, "false")
    assert is_unibet_frozen() is False
    assert is_bookmaker_frozen("unibet") is False


def test_filter_frozen_bookmaker_codes(monkeypatch):
    monkeypatch.delenv(BOOKMAKER_FREEZE_UNIBET_ENV, raising=False)
    filtered = filter_frozen_bookmaker_codes(["ladbrokes", "unibet", "betfair"])
    assert filtered == ["ladbrokes", "betfair"]


def test_subscription_service_excludes_unibet_when_frozen(monkeypatch):
    monkeypatch.delenv(BOOKMAKER_FREEZE_UNIBET_ENV, raising=False)
    service = SubscriptionService()
    premium_user = SimpleNamespace(current_plan="premium")

    allowed = service.get_allowed_bookmakers(db=None, user=premium_user)
    assert "unibet" not in allowed


def test_subscription_service_includes_unibet_when_unfrozen(monkeypatch):
    monkeypatch.setenv(BOOKMAKER_FREEZE_UNIBET_ENV, "false")
    service = SubscriptionService()
    premium_user = SimpleNamespace(current_plan="premium")

    allowed = service.get_allowed_bookmakers(db=None, user=premium_user)
    assert "unibet" in allowed
