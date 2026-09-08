"""One retry per missing upstream per day, and never on top of a running one."""
import json

from morning import config, heal


def _spy(monkeypatch, *, busy=False):
    calls = []
    monkeypatch.setattr(heal, "is_busy", lambda pattern: busy)

    class Done:
        returncode = 0

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Done()

    monkeypatch.setattr(heal.subprocess, "run", fake_run)
    return calls


def test_runs_each_missing_upstream_once(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    calls = _spy(monkeypatch)
    out = heal.heal(["ai", "kline"], "2026-09-09")
    assert len(calls) == 2
    assert out["ai"].startswith("exit 0") and "async" in out["kline"]

    # a second pass the same day does not run them again
    out2 = heal.heal(["ai", "kline"], "2026-09-09")
    assert len(calls) == 2
    assert all("already attempted" in v for v in out2.values())
    assert set(json.loads((tmp_path / "2026-09-09-heal.json").read_text())) == {"ai", "kline"}


def test_leaves_a_running_upstream_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    calls = _spy(monkeypatch, busy=True)
    out = heal.heal(["finance"], "2026-09-09")
    assert calls == [] and "still running" in out["finance"]
    assert not (tmp_path / "2026-09-09-heal.json").exists()


def test_nothing_missing_means_nothing_happens(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    calls = _spy(monkeypatch)
    assert heal.heal([], "2026-09-09") == {}
    assert calls == []


def test_every_healer_keeps_feishu_off():
    assert heal.HEALERS["ai"]["cmd"][-1].endswith("push-digest.sh")  # not push-feishu-digest.sh
    assert heal.HEALERS["finance"]["env"]["PARK_INTEL_SKIP_FEISHU"] == "1"
    assert "kline-newsletter" in heal.HEALERS["kline"]["cmd"][-1]  # plist carries --no-feishu
