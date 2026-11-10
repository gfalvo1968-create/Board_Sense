"""Paid Board Sense gate: offline isolated tests, no quota DB or remote requests."""
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from routes.paid_usage_policy import reserve_paid_case

ALICE="11111111-1111-4111-8111-111111111111"
BOB="22222222-2222-4222-8222-222222222222"
NOW=datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)


def trusted(owner=ALICE):
    return dict(customer_id=owner, trusted_source="server_to_server",
                board_sense=True, paid_access_enabled=True,
                environment="live", verified_at=NOW)


def test_valid_paid_member_reserves_one_case_regardless_of_photo_count():
    calls=[]
    def atomic(customer, day, limit):
        calls.append((customer,day,limit))
        return True,1
    decision=reserve_paid_case(ALICE,trusted(),atomic,NOW)
    assert decision.allowed
    assert decision.remaining == 24
    assert calls == [(ALICE,"2026-11-10",25)]


def test_untrusted_member_claims_never_touch_quota():
    def must_not_run(*args):
        raise AssertionError("quota must not be called")
    for decision in [
        None,
        dict(trusted(), board_sense=False),
        dict(trusted(), paid_access_enabled=False),
        dict(trusted(), trusted_source="client_header"),
        dict(trusted(), environment="sandbox"),
        dict(trusted(), customer_id=BOB),
        dict(trusted(), verified_at=NOW-timedelta(minutes=6)),
        dict(trusted(), verified_at=NOW+timedelta(seconds=1)),
    ]:
        assert not reserve_paid_case(ALICE,decision,must_not_run,NOW).allowed


def test_quota_backend_failure_denies():
    def broken(*_args):
        raise OSError("synthetic backend outage")
    decision=reserve_paid_case(ALICE,trusted(),broken,NOW)
    assert not decision.allowed
    assert decision.reason=="quota_backend_unavailable"
    assert not reserve_paid_case(ALICE,trusted(),None,NOW).allowed


def test_twenty_five_of_thirty_competing_requests_get_a_case():
    lock=Lock()
    used=[0]
    def atomic(_customer,_day,limit):
        with lock:
            if used[0]>=limit:
                return False,used[0]
            used[0]+=1
            return True,used[0]
    with ThreadPoolExecutor(max_workers=12) as executor:
        results=list(executor.map(lambda _:reserve_paid_case(ALICE,trusted(),atomic,NOW),
                                  range(30)))
    assert sum(x.allowed for x in results)==25
    assert used[0]==25
    assert all(x.limit==25 for x in results)
