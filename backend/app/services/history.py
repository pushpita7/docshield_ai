
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).resolve().parents[2] / "history.db"


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_history():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                document_id TEXT PRIMARY KEY,
                document_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                risk_score INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                findings_count INTEGER NOT NULL,
                findings_json TEXT NOT NULL,
                summary TEXT NOT NULL
            )
        """)


def save_analysis(
    document_id,
    document_name,
    risk,
    findings,
):
    created_at = datetime.now(timezone.utc).isoformat()

    with connect() as db:
        db.execute("""
            INSERT OR REPLACE INTO analyses (
                document_id, document_name, created_at,
                risk_score, risk_level, findings_count,
                findings_json, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document_id,
            document_name,
            created_at,
            risk["risk_score"],
            risk["risk_level"],
            risk["findings_count"],
            json.dumps(findings),
            risk["summary"],
        ))

    return get_analysis(document_id)


def get_analysis(document_id):
    with connect() as db:
        row = db.execute(
            "SELECT * FROM analyses WHERE document_id = ?",
            (document_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["findings"] = json.loads(result.pop("findings_json"))
    return result


def list_history():
    with connect() as db:
        rows = db.execute("""
            SELECT document_id, document_name, created_at,
                   risk_score, risk_level, findings_count, summary
            FROM analyses
            ORDER BY created_at DESC
        """).fetchall()

    return [dict(row) for row in rows]