"""CloudMart API: products and orders in PostgreSQL, carts in Redis.

Deliberately small and readable: learners read this code while debugging the
Kubernetes setup around it. Every failure is logged with its real cause.
"""
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

import psycopg
import redis
from fastapi import FastAPI, HTTPException, Path
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("cloudmart")

VERSION = os.environ.get("APP_VERSION", "0.1.0")
Session = Annotated[str, Path(pattern=r"^[A-Za-z0-9-]{8,64}$")]

SEED = [
    ("k8s-mug", "Kubernetes Mug", "Holds exactly one cup of coffee per Pod.", 1200),
    ("helm-hoodie", "Helm Hoodie", "Warm, versioned, and easy to roll back.", 4500),
    ("yaml-socks", "YAML Socks", "Indentation-sensitive. Two spaces each.", 900),
    ("docker-cap", "Container Cap", "Isolates your head from the sun.", 1800),
    ("ingress-tee", "Ingress Tee", "Routes compliments to the right service.", 2200),
    ("etcd-notebook", "etcd Notebook", "Consistent, highly available notes.", 1500),
    ("probe-stickers", "Probe Stickers", "Readiness: 100%. Liveness: also 100%.", 500),
    ("pvc-bottle", "Persistent Bottle", "Your water survives Pod restarts.", 1600),
]


def db_conninfo() -> str:
    return (f"host={os.environ.get('PGHOST', 'postgres')} port={os.environ.get('PGPORT', '5432')} "
            f"dbname={os.environ.get('PGDATABASE', 'cloudmart')} user={os.environ.get('PGUSER', 'cloudmart')} "
            f"password={os.environ.get('PGPASSWORD', '')} connect_timeout=3")


def db():
    return psycopg.connect(db_conninfo(), row_factory=dict_row)


def cache() -> redis.Redis:
    return redis.Redis(host=os.environ.get("REDIS_HOST", "redis"), port=int(os.environ.get("REDIS_PORT", "6379")),
                       socket_timeout=2, socket_connect_timeout=2, decode_responses=True)


def migrate() -> None:
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, price_cents INTEGER NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, session TEXT NOT NULL, items JSONB NOT NULL, total_cents INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
        if conn.execute("SELECT count(*) AS n FROM products").fetchone()["n"] == 0:
            conn.cursor().executemany("INSERT INTO products VALUES (%s, %s, %s, %s)", SEED)
            log.info("seeded %d products", len(SEED))


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The database may still be starting; keep trying (the readiness probe stays red meanwhile).
    for attempt in range(1, 31):
        try:
            migrate()
            log.info("database ready")
            break
        except psycopg.Error as e:
            log.warning("database not ready (attempt %d): %s", attempt, str(e).strip())
            time.sleep(2)
    yield


app = FastAPI(title="CloudMart API", version=VERSION, lifespan=lifespan, docs_url="/api/docs",
              openapi_url="/api/openapi.json")


@app.get("/api/health")
def health():
    """Liveness: the process is up. Does not touch dependencies."""
    return {"status": "ok", "version": VERSION, "pod": os.environ.get("HOSTNAME")}


@app.get("/api/ready")
def ready():
    """Readiness: can we serve requests? Checks PostgreSQL and Redis."""
    problems = {}
    try:
        with db() as conn:
            conn.execute("SELECT 1")
    except psycopg.Error as e:
        problems["postgres"] = str(e).strip()
    try:
        cache().ping()
    except redis.RedisError as e:
        problems["redis"] = str(e)
    if problems:
        log.warning("not ready: %s", problems)
        raise HTTPException(503, {"ready": False, "problems": problems})
    return {"ready": True}


@app.get("/api/products")
def products():
    with db() as conn:
        return conn.execute("SELECT * FROM products ORDER BY name").fetchall()


class CartItem(BaseModel):
    product_id: str = Field(pattern=r"^[a-z0-9-]{1,64}$")
    quantity: int = Field(ge=0, le=99)


def _cart(session: str) -> dict[str, int]:
    return {k: int(v) for k, v in cache().hgetall(f"cart:{session}").items()}


@app.get("/api/cart/{session}")
def get_cart(session: Session):
    return _cart(session)


@app.put("/api/cart/{session}")
def put_cart(item: CartItem, session: Session):
    key = f"cart:{session}"
    r = cache()
    if item.quantity == 0:
        r.hdel(key, item.product_id)
    else:
        r.hset(key, item.product_id, item.quantity)
    r.expire(key, 24 * 3600)
    return _cart(session)


@app.post("/api/orders/{session}", status_code=201)
def place_order(session: Session):
    cart = _cart(session)
    if not cart:
        raise HTTPException(400, "Your cart is empty")
    with db() as conn:
        rows = conn.execute("SELECT id, price_cents FROM products WHERE id = ANY(%s)", (list(cart),)).fetchall()
        prices = {r["id"]: r["price_cents"] for r in rows}
        items = [{"product_id": p, "quantity": q, "price_cents": prices[p]} for p, q in cart.items() if p in prices]
        total = sum(i["quantity"] * i["price_cents"] for i in items)
        order_id = uuid.uuid4().hex[:12]
        conn.execute("INSERT INTO orders (id, session, items, total_cents) VALUES (%s, %s, %s, %s)",
                     (order_id, session, json.dumps(items), total))
    cache().delete(f"cart:{session}")
    log.info("order %s placed: %d items, %d cents", order_id, len(items), total)
    return {"id": order_id, "total_cents": total, "items": items}


@app.get("/api/orders/{session}")
def orders(session: Session):
    with db() as conn:
        return conn.execute("SELECT id, items, total_cents, created_at FROM orders WHERE session = %s "
                            "ORDER BY created_at DESC LIMIT 20", (session,)).fetchall()
