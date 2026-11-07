"""Launch rehearsal: offline, bounded quota concurrency regression tests.

Run with: python -m pytest -q tests/test_launch_quota_concurrency.py
No external service requests, scan processing, network calls or user quota consumption.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

from starlette.requests import Request
from routes import free_usage_gate as gate


def visitor_request(extra=None):
    headers = [(b'user-agent', b'visitor-iphone')]
    for name, value in (extra or {}).items():
        headers.append((name.lower().encode(), value.encode()))
    return Request({
        "type": "http", "http_version": "1.1", "method": "GET",
        "scheme": "https", "path": "/free-usage", "raw_path": b"/free-usage",
        "query_string": b"", "headers": headers, "client": ("203.0.113.80", 53000),
        "server": ("testserver", 443),
    })


def production_stubs(monkeypatch):
    monkeypatch.setenv("BOARD_SENSE_ENV", "production")
    monkeypatch.setattr(gate, "BOARD_SENSE_ENV", "production")
    monkeypatch.setenv("BOARD_SENSE_VISITOR_SALT", "synthetic-offline-test-salt")
    monkeypatch.setattr(gate, "SUPABASE_URL", "https://example.invalid")
    monkeypatch.setattr(gate, "SUPABASE_SECRET", "offline-placeholder-not-a-secret")
    monkeypatch.setattr(gate, "BOARD_SENSE_TESTER_KEY", "offline-tester-only")
    monkeypatch.setattr(gate, "DAILY_FREE_BOARD_LIMIT", 1)


def test_eight_competing_visitors_share_single_public_allowance(monkeypatch):
    """The test uses one synthetic visitor, one mocked atomic claim, eight threads."""
    production_stubs(monkeypatch)
    barrier = Barrier(8)
    counter_lock = Lock()
    used = [0]

    def mocked_atomic_claim(request, visitor):
        barrier.wait(timeout=5)
        with counter_lock:
            if used[0] >= 1:
                return False, used[0]
            used[0] += 1
            return True, used[0]

    monkeypatch.setattr(gate, "_supabase_claim", mocked_atomic_claim)
    with ThreadPoolExecutor(max_workers=8) as workers:
        outcomes = list(workers.map(lambda _: gate.record_free_board_use(visitor_request(), "case"), range(8)))

    assert sum(o.allowed for o in outcomes) == 1
    assert sum(not o.allowed for o in outcomes) == 7
    assert used[0] == 1
    assert all(o.used_today == 1 for o in outcomes)
    assert {o.visitor_id for o in outcomes}.__len__() == 1


def test_failed_backend_fails_closed_not_local(monkeypatch):
    production_stubs(monkeypatch)
    def broken_claim(request, visitor):
        raise OSError("synthetic quota backend unavailable")
    monkeypatch.setattr(gate, "_supabase_claim", broken_claim)
    monkeypatch.setattr(gate, "_local_claim", lambda *_args: (_ for _ in ()).throw(AssertionError("Local fallback not allowed")))
    decision = gate.record_free_board_use(visitor_request(), "case")
    assert not decision.allowed
    assert decision.reason == "usage_backend_unavailable"
    assert gate.free_gate_payload(decision)["status"] == "temporarily_unavailable"


def test_client_header_cannot_mint_new_allowance(monkeypatch):
    production_stubs(monkeypatch)
    first = gate._visitor_id(visitor_request({"user-agent": "Mobile Safari", "x-forwarded-for": "8.8.8.8"}))
    second = gate._visitor_id(visitor_request({"user-agent": "Some Other Browser", "x-forwarded-for": "9.9.9.9"}))
    assert first == second


def test_tester_requires_exact_server_secret(monkeypatch):
    production_stubs(monkeypatch)
    assert not gate._is_authorized_tester(visitor_request())
    assert not gate._is_authorized_tester(visitor_request({"x-board-sense-tester-key": "incorrect"}))
    assert gate._is_authorized_tester(visitor_request({"x-board-sense-tester-key": "offline-tester-only"}))
