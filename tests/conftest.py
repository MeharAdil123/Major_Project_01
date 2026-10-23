"""Shared test set-up. Tests never read data/raw: they use SYNTHETIC data made in tmp_path."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
