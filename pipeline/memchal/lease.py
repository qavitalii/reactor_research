"""Local ownership and process lock for the single stateful Reactor agent."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re

LEASE_DIR = Path(os.environ.get("REACTOR_LEASE_DIR") or Path(__file__).resolve().parents[1] / "runs" / "leases")


@contextmanager
def agent_lease(agent_id):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", agent_id):
        raise ValueError("Invalid agent id for local lease")
    LEASE_DIR.mkdir(parents=True, exist_ok=True)
    reservation = LEASE_DIR / f"{agent_id}.json"
    if reservation.exists():
        state = json.loads(reservation.read_text())
        if state.get("active") and os.environ.get("REACTOR_RUN_OWNER") != state.get("owner"):
            raise RuntimeError("Reactor API is reserved by Alex for " + str(state.get("owner"))
                               + ". Do not start a competing run or reset its history.")
    with (LEASE_DIR / f"{agent_id}.lock").open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another process already holds the Reactor agent lease") from None
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
