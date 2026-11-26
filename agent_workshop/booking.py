"""Local appointment concierge: deterministic channel handler and ACID booking store.

Agent-shaped components are deliberately split from domain transaction authority.
There is no model call in offline mode, making stage demonstrations repeatable.
"""
from __future__ import annotations

import sqlite3
import tempfile
import os
from contextlib import contextmanager
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

DEMO_DATE = "2026-12-04"  # Fixed fictional Friday; not the current date.


@dataclass
class BookingReply:
    agent: str
    state: str
    message: str
    customer: str
    slot_id: str | None = None
    reference: str | None = None

    def to_dict(self):
        return asdict(self)


class BookingStore:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        if db_path == ":memory:":
            # File-backed temporary database enables WAL + real concurrent writers.
            fd, self.db_path = tempfile.mkstemp(prefix="agentworkshop-", suffix=".sqlite")
            os.close(fd)
            self._temp_path = self.db_path
        else:
            self._temp_path = None
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.uri = False
        with self.connection() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript("""
                CREATE TABLE IF NOT EXISTS slots(
                    slot_id TEXT PRIMARY KEY, clinician TEXT NOT NULL,
                    site TEXT NOT NULL, starts TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations(
                    customer TEXT PRIMARY KEY, state TEXT NOT NULL,
                    offered_slot TEXT
                );
                CREATE TABLE IF NOT EXISTS bookings(
                    reference TEXT PRIMARY KEY, customer TEXT NOT NULL,
                    slot_id TEXT NOT NULL UNIQUE,
                    FOREIGN KEY(slot_id) REFERENCES slots(slot_id)
                );
                CREATE TABLE IF NOT EXISTS incoming(
                    message_id TEXT PRIMARY KEY, response_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS escalations(
                    ticket_id TEXT PRIMARY KEY, customer TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
            """)
            con.executemany("INSERT OR IGNORE INTO slots VALUES (?,?,?,?)", [
                ("R-1730", "Dr Rao", "West Clinic", f"{DEMO_DATE} 17:30"),
                ("R-1800", "Dr Rao", "West Clinic", f"{DEMO_DATE} 18:00"),
                ("S-1600", "Dr Shah", "East Clinic", f"{DEMO_DATE} 16:00"),
            ])

    @contextmanager
    def connection(self):
        con = sqlite3.connect(self.db_path, timeout=20, isolation_level=None)
        try:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA busy_timeout = 20000")
            yield con
        finally:
            con.close()

    def __del__(self):
        temp = getattr(self, "_temp_path", None)
        if temp:
            for suffix in ("", "-wal", "-shm"):
                try:
                    os.unlink(temp + suffix)
                except OSError:
                    pass

    def summary(self):
        with self.connection() as con:
            return {
                "bookings": con.execute("SELECT count(*) FROM bookings").fetchone()[0],
                "escalations": con.execute("SELECT count(*) FROM escalations").fetchone()[0],
                "messages": con.execute("SELECT count(*) FROM incoming").fetchone()[0],
                "available_slots": [dict(x) for x in con.execute("""SELECT s.* FROM slots s
                  WHERE NOT EXISTS(SELECT 1 FROM bookings b WHERE b.slot_id=s.slot_id)
                  ORDER BY starts""")],
            }


class Concierge:
    """Supervisor directs to availability, booking, or human escalation specialists."""
    def __init__(self, store: BookingStore):
        self.store = store

    def on_message(self, customer: str, message: str, message_id: str) -> BookingReply:
        import json
        customer, message, message_id = customer.strip(), message.strip(), message_id.strip()
        if not customer or not message or not message_id:
            raise ValueError("customer, message and message_id are required")
        if len(customer) > 100 or len(message) > 2000 or len(message_id) > 128:
            raise ValueError("input exceeds demo limits")
        with self.store.connection() as con:
            con.execute("BEGIN IMMEDIATE")
            duplicate = con.execute("SELECT response_json FROM incoming WHERE message_id=?", (message_id,)).fetchone()
            if duplicate:
                con.execute("COMMIT")
                return BookingReply(**json.loads(duplicate[0]))
            reply = self._route(con, customer, message)
            con.execute("INSERT INTO incoming VALUES (?,?)", (message_id, json.dumps(reply.to_dict())))
            con.execute("COMMIT")
            return reply

    def _route(self, con, customer, message):
        m = message.lower().strip()
        if any(x in m for x in ("human", "supervisor", "call me", "complex", "urgent", "chest pain")):
            # No medical interpretation; simply escalate or advise emergency assistance.
            ticket = "H-" + uuid.uuid4().hex[:8].upper()
            con.execute("INSERT INTO escalations VALUES (?,?,?)", (ticket, customer, "Requested human assistance / urgent wording"))
            con.execute("INSERT OR REPLACE INTO conversations VALUES (?,?,NULL)", (customer, "ESCALATED"))
            emergency = " For a medical emergency, contact local emergency services immediately." if any(x in m for x in ("urgent", "chest pain")) else ""
            return BookingReply("Human Escalation", "ESCALATED",
                f"I've created a human callback request ({ticket}). Staff will follow up through an approved channel." + emergency, customer)
        state = con.execute("SELECT * FROM conversations WHERE customer=?", (customer,)).fetchone()
        if m in ("yes", "confirm", "book it"):
            if not state or state["state"] != "OFFERED":
                return BookingReply("Supervisor", "NEED_INFO", "Please request an available appointment first.", customer)
            slot_id = state["offered_slot"]
            ref = "BK-" + uuid.uuid4().hex[:8].upper()
            try:
                con.execute("INSERT INTO bookings VALUES (?,?,?)", (ref, customer, slot_id))
            except sqlite3.IntegrityError:
                con.execute("UPDATE conversations SET state='CONFLICT' WHERE customer=?", (customer,))
                return BookingReply("Booking Domain Service", "CONFLICT",
                    "That slot has just been reserved. Please ask for another available slot.", customer, slot_id)
            con.execute("UPDATE conversations SET state='CONFIRMED' WHERE customer=?", (customer,))
            actual = con.execute("SELECT clinician,site,starts FROM slots WHERE slot_id=?", (slot_id,)).fetchone()
            return BookingReply("Booking Domain Service", "CONFIRMED",
                f"Confirmed! Appointment {ref} with {actual['clinician']} at {actual['site']} on {actual['starts']} (demo fixture).",
                customer, slot_id, ref)
        if m in ("no", "cancel"):
            con.execute("INSERT OR REPLACE INTO conversations VALUES (?,?,NULL)", (customer, "CANCELLED"))
            return BookingReply("Supervisor", "CANCELLED", "No booking was made.", customer)
        if "rao" in m or "appointment" in m or "clinic" in m or "friday" in m:
            # For the stage demo, the intake specialist maps one known user intent to a fixed fixture.
            # A live deployment needs a real NLU/agent path, timezone normalization, and identity verification.
            slot = con.execute("""SELECT s.* FROM slots s WHERE clinician='Dr Rao'
                AND starts LIKE ? AND NOT EXISTS(SELECT 1 FROM bookings b WHERE b.slot_id=s.slot_id)
                ORDER BY s.starts LIMIT 1""", (DEMO_DATE + '%',)).fetchone()
            if slot is None:
                return BookingReply("Availability Agent", "NO_SLOTS", "No free Dr Rao slots remain in the demo calendar.", customer)
            con.execute("INSERT OR REPLACE INTO conversations VALUES (?,?,?)", (customer, "OFFERED", slot["slot_id"]))
            return BookingReply("Availability Agent", "OFFERED",
                f"I found Dr Rao at West Clinic on {DEMO_DATE} at {slot['starts'][-5:]}. Reply YES to confirm (demo date).",
                customer, slot["slot_id"])
        return BookingReply("Intake Agent", "NEED_INFO", "Which clinician or clinic would you like? Example: Dr Rao on Friday after 5 PM.", customer)


def run_slot_race(contenders: int = 20):
    """Independent customers offered one *same* slot, then confirm concurrently."""
    store = BookingStore()
    agent = Concierge(store)
    for i in range(contenders):
        customer = f"customer-{i:02d}"
        with store.connection() as con:
            con.execute("INSERT INTO conversations VALUES (?,?,?)", (customer, "OFFERED", "R-1730"))
    barrier = threading.Barrier(contenders)
    def work(i):
        barrier.wait(timeout=10)
        return agent.on_message(f"customer-{i:02d}", "YES", f"race-confirm-{i}").state
    with ThreadPoolExecutor(max_workers=contenders) as pool:
        results = list(pool.map(work, range(contenders)))
    return {"contenders": contenders, "confirmed": results.count("CONFIRMED"),
            "conflicts": results.count("CONFLICT"), "booking_rows": store.summary()["bookings"]}
