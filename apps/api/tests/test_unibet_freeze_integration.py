from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.core.auth import UserClaims, get_current_user
from api.core.bookmaker_freeze import BOOKMAKER_FREEZE_UNIBET_ENV
from api.core.database import get_db
from api.main import app
from api.routers import metadata as metadata_router
from jobs.scrape_service import ScrapeService


class _DummyField:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)

    def in_(self, values):
        return ("in", self.name, list(values))


class _FakeUserModel:
    clerk_user_id = _DummyField("clerk_user_id")

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")
        self.clerk_user_id = kwargs.get("clerk_user_id")
        self.email = kwargs.get("email")
        self.email_verified = kwargs.get("email_verified")
        self.current_plan = kwargs.get("current_plan", "free")
        self.plan_status = kwargs.get("plan_status", "active")


class _FakeBookmakerModel:
    code = _DummyField("code")
    display_name = _DummyField("display_name")


class _FakeQuery:
    def __init__(self, rows):
        self._rows = list(rows)
        self._conditions = []

    def filter(self, *conditions):
        self._conditions.extend(conditions)
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def _apply(self):
        rows = self._rows
        for cond in self._conditions:
            if not isinstance(cond, tuple) or len(cond) != 3:
                continue
            op, field, value = cond
            if op == "eq":
                rows = [r for r in rows if getattr(r, field, None) == value]
            elif op == "in":
                rows = [r for r in rows if getattr(r, field, None) in value]
        return rows

    def first(self):
        rows = self._apply()
        return rows[0] if rows else None

    def all(self):
        rows = self._apply()
        return sorted(rows, key=lambda r: getattr(r, "display_name", ""))


class _FakeMetadataDbSession:
    def __init__(self):
        self.users = []
        self.bookmakers = [
            SimpleNamespace(
                id=1,
                code="ladbrokes",
                display_name="Ladbrokes",
                scraping_config={"tier": "free"},
            ),
            SimpleNamespace(
                id=2,
                code="unibet",
                display_name="Unibet",
                scraping_config={"tier": "premium"},
            ),
        ]

    def query(self, model):
        if model is _FakeUserModel:
            return _FakeQuery(self.users)
        if model is _FakeBookmakerModel:
            return _FakeQuery(self.bookmakers)
        return _FakeQuery([])

    def add(self, obj):
        if isinstance(obj, _FakeUserModel):
            if obj.id is None:
                obj.id = len(self.users) + 1
            self.users.append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def close(self):
        return None


class _FakeWorkerBookmakerModel:
    # Value is irrelevant; FakeQuery.filter is a no-op for worker path.
    is_active = True


class _FakeWorkerQuery:
    def __init__(self, rows):
        self._rows = list(rows)

    def filter(self, *_args, **_kwargs):
        return self

    def all(self):
        return self._rows


class _FakeWorkerDbSession:
    def __init__(self):
        self._rows = [
            SimpleNamespace(
                code="ladbrokes",
                name="Ladbrokes",
                base_url="https://www.ladbrokes.com.au",
                website_url="https://www.ladbrokes.com.au",
                lifecycle_state="active",
                is_active=True,
                scraping_config={"scraper_class": "entain"},
            ),
            SimpleNamespace(
                code="unibet",
                name="Unibet",
                base_url="https://www.unibet.com.au",
                website_url="https://www.unibet.com.au",
                lifecycle_state="active",
                is_active=True,
                scraping_config={"scraper_class": "kindred"},
            ),
        ]

    def query(self, _model):
        if _model is _FakeWorkerBookmakerModel:
            return _FakeWorkerQuery(self._rows)
        # Rollout policy tables are empty in this integration fixture.
        return _FakeWorkerQuery([])

    def close(self):
        return None


def test_unibet_freeze_hides_metadata_and_active_scrape_selection(monkeypatch):
    # Keep freeze enabled (default behavior) for this integration check.
    monkeypatch.delenv(BOOKMAKER_FREEZE_UNIBET_ENV, raising=False)

    # -------- Metadata exposure path --------
    fake_metadata_db = _FakeMetadataDbSession()
    monkeypatch.setattr(metadata_router, "User", _FakeUserModel)
    monkeypatch.setattr(metadata_router, "Bookmaker", _FakeBookmakerModel)

    def override_get_db():
        yield fake_metadata_db

    def override_current_user():
        return UserClaims(sub="user_freeze_test", email="freeze@test.local", email_verified=True)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)
        response = client.get("/metadata/bookmakers")
        assert response.status_code == 200
        codes = [bm["code"] for bm in response.json()]
        assert "ladbrokes" in codes
        assert "unibet" not in codes
    finally:
        app.dependency_overrides.clear()

    # -------- Active scrape selection path --------
    import api.core.database as db_core
    import api.models as api_models

    monkeypatch.setattr(db_core, "SessionLocal", lambda: _FakeWorkerDbSession())
    monkeypatch.setattr(api_models, "Bookmaker", _FakeWorkerBookmakerModel)

    service = ScrapeService()
    active = service.get_active_bookmakers_from_db()
    active_codes = [bm["code"] for bm in active]

    assert "ladbrokes" in active_codes
    assert "unibet" not in active_codes
