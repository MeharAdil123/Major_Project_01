"""Features f2: shapes, names, groups, finite values, and that dynamic features see motion."""
import numpy as np
import pytest

from ml import features as fx


def win(T, moving=False, seed=0):
    rng = np.random.default_rng(seed)
    S = 114
    t = np.arange(T) / 100
    base = 1 + 0.2 * np.sin(np.arange(S) / 7)
    X = np.tile(base, (2, T, 1)) * (1 + 0.01 * rng.standard_normal((2, T, S)))
    P = 0.05 * rng.standard_normal((2, T, S))
    if moving:
        X = X * (1 + 0.2 * np.sin(2 * np.pi * 1.5 * t)[None, :, None] * np.cos(np.arange(S) / 4)[None, None, :])
        P = P + 0.5 * np.sin(2 * np.pi * 1.5 * t)[None, :, None]
    rssi = -40 + rng.standard_normal((2, T))
    return X.astype(np.float32), P.astype(np.float32), rssi.astype(np.float32)


@pytest.mark.parametrize("T", [200, 300, 400])
def test_shape_names_groups(T):
    f = fx.window_features(*win(T))
    names = fx.feature_names()
    groups = fx.feature_groups()
    assert f.shape == (len(names),) and np.all(np.isfinite(f))
    assert len(set(names)) == len(names) and set(groups) == set(names)
    assert {g for g, _ in groups.values()} == {"static", "dynamic"}
    assert not any(k in n for n in names for k in ("miss", "loss", "low_scale"))


def test_static_group_holds_level_and_shape():
    g = fx.feature_groups()
    assert g["rx1_rssi_mean"][0] == "static" and g["rx2_band3_mean"][0] == "static"
    assert g["rx1_pca_evr1"][0] == "static" and g["xrx_rssi_diff"][0] == "static"
    assert g["rx1_rssi_std"][0] == "dynamic" and g["rx2_ph_cvar_w"] == ("dynamic", "phase")


def test_dynamic_features_increase_with_motion():
    names = fx.feature_names()
    still = dict(zip(names, fx.window_features(*win(300))))
    mov = dict(zip(names, fx.window_features(*win(300, moving=True))))
    for n in ("rx1_sd_mean", "rx1_motion_max", "rx1_ph_cvar_w", "rx2_dph_w", "rx1_sc_corr"):
        assert mov[n] > still[n], n
    assert abs(mov["rx1_pc1_peak_hz"] - 1.5) < 0.4


def test_batch_matches_single():
    X, P, r = win(300)
    B = fx.batch_features(np.stack([X, X]), np.stack([P, P]), np.stack([r, r]))
    np.testing.assert_allclose(B[0], fx.window_features(X, P, r))
