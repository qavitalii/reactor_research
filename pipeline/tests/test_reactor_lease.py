import json

import pytest

import memchal.lease as reactor_lease


def test_active_reservation_rejects_other_owner_before_network(tmp_path, monkeypatch):
    monkeypatch.setattr(reactor_lease, "LEASE_DIR", tmp_path)
    (tmp_path / "agt_test.json").write_text(json.dumps({"owner": "a", "active": True}))
    monkeypatch.delenv("REACTOR_RUN_OWNER", raising=False)
    with pytest.raises(RuntimeError, match="reserved by Alex"):
        with reactor_lease.agent_lease("agt_test"):
            pytest.fail("must not reach any network work")
    monkeypatch.setenv("REACTOR_RUN_OWNER", "a")
    with reactor_lease.agent_lease("agt_test"):
        pass


def test_same_owner_still_cannot_make_parallel_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(reactor_lease, "LEASE_DIR", tmp_path)
    with reactor_lease.agent_lease("agt_test"):
        with pytest.raises(RuntimeError, match="already holds"):
            with reactor_lease.agent_lease("agt_test"):
                pytest.fail("must not allow a second client")
    with reactor_lease.agent_lease("agt_test"):
        pass
