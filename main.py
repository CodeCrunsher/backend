"""
Batcomputer API  —  Year 2089
FastAPI backend with SQLite persistence and Gemini AI overwatch (Oracle).
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Environment ──────────────────────────────────────────────────────────────
load_dotenv()  # reads .env if present (never hardcode keys)
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

_genai_available = False
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        _genai_available = True
    except ImportError:
        pass

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Batcomputer API",
    description="Year 2089 — Gotham City tactical overwatch system.",
    version="2089.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "batcomputer.db")

ORACLE_SYSTEM_PROMPT = (
    "You are Oracle (Barbara Gordon) operating the Batcomputer in the year 2089. "
    "You are Batman's tactical overwatch. Respond to his messages concisely, professionally, "
    "and with a dark, cyberpunk, tactical tone. Keep responses under 3 sentences. "
    "Do not break character."
)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS missions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            description  TEXT,
            priority     INTEGER NOT NULL DEFAULT 2,
            is_completed INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS equipment (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            status          TEXT    NOT NULL DEFAULT 'OPERATIONAL',
            integrity_level INTEGER NOT NULL DEFAULT 100
        );

        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            sender    TEXT NOT NULL,
            content   TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    """)

    # Seed missions if empty
    if cur.execute("SELECT COUNT(*) FROM missions").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO missions (title, description, priority, is_completed) VALUES (?,?,?,?)",
            [
                ("Neutralize Scarecrow's Fear Gas Lab",
                 "Intel confirms lab in The Narrows producing weaponised fear toxin. "
                 "Eliminate the threat before 0300.", 1, 0),
                ("Intercept Penguin Arms Shipment",
                 "Cobblepot moving military-grade hardware through Gotham Harbour. "
                 "Dock 7 — window closes at 0200.", 1, 0),
                ("Track The Riddler's Encrypted Signal",
                 "Transmission traced to Old Gotham Tower. Decrypt and locate source.", 2, 0),
                ("Surveil Maroni Syndicate Safehouse",
                 "Place quantum tap on Midtown safehouse. Extract comms data undetected.", 2, 0),
                ("Recover Stolen Wayne Tech Prototype",
                 "EMP gauntlet stolen from R&D vault. Retrieval priority: ALPHA.", 1, 0),
            ],
        )

    # Seed equipment if empty
    if cur.execute("SELECT COUNT(*) FROM equipment").fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO equipment (name, status, integrity_level) VALUES (?,?,?)",
            [
                ("Mark VII Batsuit",         "OPERATIONAL", 94),
                ("Batmobile Mk.IV",          "OPERATIONAL", 88),
                ("Batwing Stealth Drone",    "STANDBY",     75),
                ("Batarangs  ×24",           "READY",      100),
                ("Grapple Gun",              "OPERATIONAL",  97),
                ("Nano-EMP Device",          "CHARGING",    60),
                ("Explosive Gel Dispenser",  "READY",       100),
                ("AR Combat Goggles",        "OPERATIONAL",  82),
            ],
        )

    conn.commit()
    conn.close()


# ── Pydantic models ───────────────────────────────────────────────────────────
class MessageIn(BaseModel):
    sender: str
    content: str


class MessageOut(BaseModel):
    id: int
    sender: str
    content: str
    timestamp: str
    ai_response: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["status"])
def root():
    return {
        "system": "Batcomputer 2089",
        "status": "online",
        "uplink": "SECURE",
        "oracle": "active" if _genai_available else "offline — GEMINI_API_KEY not set",
    }


@app.get("/missions", tags=["missions"])
def list_missions():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM missions ORDER BY priority ASC, id ASC"
    ).fetchall()]
    conn.close()
    return rows


@app.get("/missions/{mission_id}", tags=["missions"])
def get_mission(mission_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM missions WHERE id=?", (mission_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Mission not found")
    return dict(row)


@app.patch("/missions/{mission_id}/complete", tags=["missions"])
def complete_mission(mission_id: int):
    conn = get_conn()
    conn.execute("UPDATE missions SET is_completed=1 WHERE id=?", (mission_id,))
    conn.commit()
    conn.close()
    return {"status": "mission completed", "id": mission_id}


@app.get("/equipment", tags=["equipment"])
def list_equipment():
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM equipment ORDER BY id ASC"
    ).fetchall()]
    conn.close()
    return rows


@app.get("/messages", tags=["comms"])
def list_messages(limit: int = 50):
    conn = get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM messages ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()]
    conn.close()
    return rows


@app.post("/messages", response_model=MessageOut, tags=["comms"])
def send_message(body: MessageIn) -> MessageOut:
    """Receive a message from Batman, generate an Oracle AI response, persist both."""
    conn = get_conn()
    ts = datetime.now(timezone.utc).isoformat()

    # Persist incoming message
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO messages (sender, content, timestamp) VALUES (?,?,?)",
        (body.sender, body.content, ts),
    )
    msg_id = cur.lastrowid

    # Oracle AI response
    ai_response: str | None = None
    if _genai_available:
        try:
            model = genai.GenerativeModel("gemini-2.0-flash")
            result = model.generate_content(
                f"{ORACLE_SYSTEM_PROMPT}\n\nBatman: {body.content}"
            )
            ai_response = result.text.strip()
            # Persist Oracle's reply
            conn.execute(
                "INSERT INTO messages (sender, content, timestamp) VALUES (?,?,?)",
                ("Oracle", ai_response, datetime.now(timezone.utc).isoformat()),
            )
        except Exception as exc:  # never crash on AI errors
            ai_response = (
                f"[Batcomputer signal degraded — Oracle offline. Error: {type(exc).__name__}]"
            )
    else:
        ai_response = (
            "[Oracle offline — GEMINI_API_KEY not configured on server.]"
        )

    conn.commit()
    conn.close()

    return MessageOut(
        id=msg_id,
        sender=body.sender,
        content=body.content,
        timestamp=ts,
        ai_response=ai_response,
    )


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)


@app.on_event("startup")
def on_startup():
    init_db()
