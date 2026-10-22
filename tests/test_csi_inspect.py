"""csi_inspect output folder rules (D-022) and an end-to-end run on SYNTHETIC data."""
import json
import os
import sys

import pytest

from host import csi_inspect as ci


def test_default_out_uses_session_id(tmp_path):
    run = tmp_path / "somewhere" / "folder_name"
    run.mkdir(parents=True)
    (run / "meta.json").write_text(json.dumps({"session_id": "20261022_S1_E04_stand_up"}))
    out = ci.resolve_out(run, None, None, None, out_root=tmp_path / "results" / "signal")
    assert out == tmp_path / "results" / "signal" / "20261022_S1_E04_stand_up"
    out = ci.resolve_out(run, None, 2.0, None, out_root=tmp_path / "res")
    assert out.name == "20261022_S1_E04_stand_up_t2.0-end"


def test_default_root_is_results_signal(tmp_path):
    run = tmp_path / "e0_swap"; run.mkdir()
    assert ci.resolve_out(run, None, None, None) == ci.ROOT / "results" / "signal" / "e0_swap"


@pytest.mark.parametrize("rel", ["data/raw/x", "data/raw/_rejected/y", "a/data/raw", "data/raw/x/inspect"])
def test_refuses_raw(tmp_path, rel):
    with pytest.raises(ValueError):
        ci.resolve_out(tmp_path, tmp_path / rel, None, None)


def test_refuses_raw_through_symlink(tmp_path):
    (tmp_path / "data" / "raw").mkdir(parents=True)
    os.symlink(tmp_path / "data" / "raw", tmp_path / "innocent")
    with pytest.raises(ValueError):
        ci.resolve_out(tmp_path, tmp_path / "innocent" / "out", None, None)


def test_default_for_a_take_in_raw_goes_to_results(tmp_path):
    take = tmp_path / "data" / "raw" / "20261022_S2_T03_sit"
    take.mkdir(parents=True)
    out = ci.resolve_out(take, None, None, None, out_root=tmp_path / "results" / "signal")
    assert not ci.inside_raw(out)


def test_main_refuses_raw_before_reading(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["csi_inspect", str(tmp_path), "--out", str(tmp_path / "data" / "raw" / "o")])
    assert ci.main() == 2
    assert not (tmp_path / "data").exists()
    assert "refusing" in capsys.readouterr().out


def test_end_to_end_synthetic(tmp_path, monkeypatch):
    from host.tests import make_synthetic_run as msr
    import numpy as np
    run = tmp_path / "run"; run.mkdir()
    rng = np.random.default_rng(0)
    msr.make(run / "RX1.bin", 1, 6, 0.01, rng)
    msr.make(run / "RX2.bin", 2, 6, 0.02, rng)
    before = sorted(p.name for p in run.iterdir())
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["csi_inspect", str(run), "--out", str(out)])
    assert ci.main() == 0
    assert sorted(p.name for p in run.iterdir()) == before          # run folder untouched
    rep = json.loads((out / "report.json").read_text())
    assert rep["receivers"]["RX1"]["htltf_used_count"] == 114
    assert {p.name for p in out.iterdir()} >= {"1_heatmap.png", "2_channel.png", "3_quality.png"}
