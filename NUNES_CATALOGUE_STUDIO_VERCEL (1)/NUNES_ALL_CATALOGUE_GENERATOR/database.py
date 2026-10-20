"""
Unified persistent database layer for NUNES Catalogue Generator.
Supports PostgreSQL (Vercel Postgres, Supabase, Neon) when POSTGRES_URL or DATABASE_URL is set,
with automatic fallback to local SQLite for local execution and offline testing.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
DATA_DIR = Path("/tmp/nunes_catalogue") if os.environ.get("VERCEL") else ROOT
DATA_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_PATH = DATA_DIR / "nunes_catalog.sqlite3"

_pg_available = False
try:
    import pg8000.native
    _pg_available = True
except ImportError:
    _pg_available = False


def _get_postgres_conn():
    """Connect to PostgreSQL using pure-Python pg8000."""
    url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL") or ""
    if not url or not _pg_available:
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        ssl_context = True if "sslmode" in params or "ssl" in parsed.query or "neon" in parsed.netloc or "supabase" in parsed.netloc or "vercel-storage" in parsed.netloc else False
        
        conn = pg8000.native.Connection(
            user=parsed.username or "postgres",
            password=parsed.password or "",
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            database=parsed.path.lstrip("/") or "postgres",
            ssl_context=ssl_context,
            timeout=10,
        )
        return conn
    except Exception as exc:
        print(f"[DB] PostgreSQL connection error: {exc}. Falling back to SQLite.")
        return None


def _get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize tables in either PostgreSQL or SQLite."""
    pg = _get_postgres_conn()
    if pg:
        try:
            pg.run("""
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    model VARCHAR(120),
                    manufacturer VARCHAR(150),
                    brand VARCHAR(150),
                    category VARCHAR(120),
                    description TEXT,
                    specs_json TEXT,
                    features_json TEXT,
                    applications_json TEXT,
                    keywords_json TEXT,
                    summary TEXT,
                    image_url TEXT,
                    image_data TEXT,
                    status VARCHAR(50) DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            pg.run("""
                CREATE TABLE IF NOT EXISTS pdf_metadata (
                    id SERIAL PRIMARY KEY,
                    product_name VARCHAR(255) NOT NULL,
                    model VARCHAR(120),
                    pdf_type VARCHAR(50) DEFAULT 'full',
                    file_size INTEGER DEFAULT 0,
                    filename VARCHAR(255),
                    download_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            pg.run("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    key VARCHAR(100) PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            pg.run("""
                CREATE TABLE IF NOT EXISTS activity_history (
                    id SERIAL PRIMARY KEY,
                    action VARCHAR(100),
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            pg.close()
            return
        except Exception as exc:
            print(f"[DB] PG table creation failed: {exc}. Reverting to SQLite.")

    # SQLite Setup
    with _get_sqlite_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                model TEXT,
                manufacturer TEXT,
                brand TEXT,
                category TEXT,
                description TEXT,
                specs_json TEXT,
                features_json TEXT,
                applications_json TEXT,
                keywords_json TEXT,
                summary TEXT,
                image_url TEXT,
                image_data TEXT,
                status TEXT DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pdf_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                model TEXT,
                pdf_type TEXT DEFAULT 'full',
                file_size INTEGER DEFAULT 0,
                filename TEXT,
                download_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()


# --- Database helper operations ---

def is_postgres_connected() -> bool:
    pg = _get_postgres_conn()
    if pg:
        try:
            pg.close()
            return True
        except Exception:
            return False
    return False


def get_products(query: str = "", category: str = "", limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Retrieve products matching filters."""
    query = query.strip().lower()
    category = category.strip().lower()

    pg = _get_postgres_conn()
    if pg:
        try:
            clauses = ["1=1"]
            params = []
            if query:
                clauses.append("(LOWER(title) LIKE :q OR LOWER(model) LIKE :q OR LOWER(description) LIKE :q)")
                params.append({"q": f"%{query}%"})
            if category:
                clauses.append("LOWER(category) = :cat")
                params.append({"cat": category})

            sql = f"SELECT * FROM products WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT {limit} OFFSET {offset}"
            rows = pg.run(sql)
            pg.close()
            # Convert tuples to dict
            cols = ["id", "title", "model", "manufacturer", "brand", "category", "description", 
                    "specs_json", "features_json", "applications_json", "keywords_json", "summary", 
                    "image_url", "image_data", "status", "created_at", "updated_at"]
            results = []
            for r in rows:
                item = dict(zip(cols, r))
                item["specs"] = json.loads(item.get("specs_json") or "[]")
                item["features"] = json.loads(item.get("features_json") or "[]")
                item["applications"] = json.loads(item.get("applications_json") or "[]")
                item["keywords"] = json.loads(item.get("keywords_json") or "[]")
                results.append(item)
            return results
        except Exception as exc:
            print(f"[DB] PG get_products error: {exc}")

    # SQLite
    with _get_sqlite_conn() as conn:
        clauses = ["1=1"]
        params = []
        if query:
            clauses.append("(LOWER(title) LIKE ? OR LOWER(model) LIKE ? OR LOWER(description) LIKE ?)")
            q = f"%{query}%"
            params.extend([q, q, q])
        if category:
            clauses.append("LOWER(category) = ?")
            params.append(category)

        sql = f"SELECT * FROM products WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        results = []
        for r in rows:
            item = dict(r)
            item["specs"] = json.loads(item.get("specs_json") or "[]")
            item["features"] = json.loads(item.get("features_json") or "[]")
            item["applications"] = json.loads(item.get("applications_json") or "[]")
            item["keywords"] = json.loads(item.get("keywords_json") or "[]")
            results.append(item)
        return results


def get_product(product_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve single product by ID."""
    with _get_sqlite_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["specs"] = json.loads(item.get("specs_json") or "[]")
        item["features"] = json.loads(item.get("features_json") or "[]")
        item["applications"] = json.loads(item.get("applications_json") or "[]")
        item["keywords"] = json.loads(item.get("keywords_json") or "[]")
        return item


def save_product(data: Dict[str, Any]) -> int:
    """Create or update a product."""
    title = str(data.get("title") or data.get("product_name") or data.get("product") or "").strip()
    model = str(data.get("model") or "").strip()
    manufacturer = str(data.get("manufacturer") or "").strip()
    brand = str(data.get("brand") or "").strip()
    category = str(data.get("category") or "").strip()
    description = str(data.get("description") or "").strip()
    summary = str(data.get("summary") or "").strip()
    image_url = str(data.get("image_url") or data.get("image") or "").strip()
    image_data = str(data.get("image_data") or "").strip()
    status = str(data.get("status") or "draft").strip()

    specs = data.get("specs") or data.get("specifications") or []
    if isinstance(specs, str):
        # convert string to list of pairs
        specs = [{"key": k.strip(), "value": v.strip()} for part in specs.split(";") if ":" in part for k, v in [part.split(":", 1)]]
    specs_json = json.dumps(specs)

    features = data.get("features") or data.get("key_features") or []
    if isinstance(features, str):
        features = [x.strip() for x in features.split(";") if x.strip()]
    features_json = json.dumps(features)

    applications = data.get("applications") or []
    if isinstance(applications, str):
        applications = [x.strip() for x in applications.split(";") if x.strip()]
    applications_json = json.dumps(applications)

    keywords = data.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [x.strip() for x in keywords.split(",") if x.strip()]
    keywords_json = json.dumps(keywords)

    product_id = data.get("id")

    with _get_sqlite_conn() as conn:
        if product_id:
            conn.execute("""
                UPDATE products SET
                    title=?, model=?, manufacturer=?, brand=?, category=?,
                    description=?, specs_json=?, features_json=?, applications_json=?,
                    keywords_json=?, summary=?, image_url=?, image_data=?, status=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (title, model, manufacturer, brand, category, description, specs_json,
                  features_json, applications_json, keywords_json, summary, image_url, image_data, status, product_id))
            conn.commit()
            return int(product_id)
        else:
            cur = conn.execute("""
                INSERT INTO products (
                    title, model, manufacturer, brand, category,
                    description, specs_json, features_json, applications_json,
                    keywords_json, summary, image_url, image_data, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (title, model, manufacturer, brand, category, description, specs_json,
                  features_json, applications_json, keywords_json, summary, image_url, image_data, status))
            conn.commit()
            return cur.lastrowid


def delete_product(product_id: int) -> bool:
    with _get_sqlite_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))
        conn.commit()
        return True


def record_pdf_generation(product_name: str, model: str, pdf_type: str, file_size: int, filename: str) -> None:
    with _get_sqlite_conn() as conn:
        conn.execute("""
            INSERT INTO pdf_metadata (product_name, model, pdf_type, file_size, filename, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (product_name, model, pdf_type, file_size, filename))
        conn.commit()


def get_pdf_history(limit: int = 50) -> List[Dict[str, Any]]:
    with _get_sqlite_conn() as conn:
        rows = conn.execute("SELECT * FROM pdf_metadata ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def log_activity(action: str, details: str = "") -> None:
    with _get_sqlite_conn() as conn:
        conn.execute("INSERT INTO activity_history (action, details) VALUES (?, ?)", (action, details))
        conn.commit()


def get_activity_history(limit: int = 30) -> List[Dict[str, Any]]:
    with _get_sqlite_conn() as conn:
        rows = conn.execute("SELECT * FROM activity_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# Auto-initialize on module load
try:
    init_db()
except Exception as e:
    print(f"[DB] Initial setup error: {e}")
