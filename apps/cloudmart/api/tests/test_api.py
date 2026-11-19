"""CloudMart API with in-memory stand-ins for PostgreSQL and Redis."""
import psycopg
import pytest
import redis
from fastapi.testclient import TestClient

from app import main

SID = "session-1234"


class FakeRedis:
    store: dict = {}

    def __init__(self, fail=False):
        self.fail = fail

    def ping(self):
        if self.fail:
            raise redis.ConnectionError("Error 111 connecting to redis:6379. Connection refused.")
        return True

    def hgetall(self, k):
        return dict(self.store.get(k, {}))

    def hset(self, k, f, v):
        self.store.setdefault(k, {})[f] = str(v)

    def hdel(self, k, f):
        self.store.get(k, {}).pop(f, None)

    def expire(self, *_):
        pass

    def delete(self, k):
        self.store.pop(k, None)


class FakeConn:
    orders: list = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        rows = []
        if "FROM products WHERE id = ANY" in sql:
            rows = [{"id": i, "price_cents": p} for i, _, _, p in main.SEED if i in params[0]]
        elif "FROM products" in sql:
            rows = [{"id": i, "name": n, "description": d, "price_cents": p} for i, n, d, p in main.SEED]
        elif sql.startswith("INSERT INTO orders"):
            self.orders.append(params)
        return type("R", (), {"fetchall": lambda _s: rows, "fetchone": lambda _s: {"n": len(main.SEED)}})()


@pytest.fixture()
def client(monkeypatch):
    FakeRedis.store, FakeConn.orders = {}, []
    monkeypatch.setattr(main, "cache", lambda: FakeRedis())
    monkeypatch.setattr(main, "db", lambda: FakeConn())
    with TestClient(main.app) as c:
        yield c


def test_health_never_touches_dependencies(client, monkeypatch):
    monkeypatch.setattr(main, "db", lambda: (_ for _ in ()).throw(AssertionError("db used")))
    assert client.get("/api/health").json()["status"] == "ok"


def test_ready_reports_which_dependency_is_down(client, monkeypatch):
    monkeypatch.setattr(main, "cache", lambda: FakeRedis(fail=True))
    r = client.get("/api/ready")
    assert r.status_code == 503
    assert "redis" in r.json()["detail"]["problems"] and "postgres" not in r.json()["detail"]["problems"]


def test_ready_reports_database_errors(client, monkeypatch):
    def broken():
        raise psycopg.OperationalError('connection to server at "postgres" failed: password authentication failed')
    monkeypatch.setattr(main, "db", broken)
    assert "password authentication failed" in client.get("/api/ready").json()["detail"]["problems"]["postgres"]


def test_shop_flow(client):
    assert len(client.get("/api/products").json()) == len(main.SEED)
    assert client.put(f"/api/cart/{SID}", json={"product_id": "k8s-mug", "quantity": 2}).json() == {"k8s-mug": 2}
    client.put(f"/api/cart/{SID}", json={"product_id": "yaml-socks", "quantity": 1})
    order = client.post(f"/api/orders/{SID}").json()
    assert order["total_cents"] == 2 * 1200 + 900
    assert client.get(f"/api/cart/{SID}").json() == {}
    assert client.post(f"/api/orders/{SID}").status_code == 400  # empty cart


def test_bad_session_rejected(client):
    assert client.get("/api/cart/x").status_code == 422
