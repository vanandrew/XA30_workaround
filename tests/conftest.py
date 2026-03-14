import numpy as np
import pytest
from pathlib import Path


@pytest.fixture
def tmp_dat_file(tmp_path):
    """Create a temporary .dat file with known uint16 data."""

    def _make_dat(data: np.ndarray, name: str = "test.dat") -> Path:
        dat_path = tmp_path / name
        data.astype(np.uint16).tofile(dat_path)
        return dat_path

    return _make_dat


@pytest.fixture
def sample_shape():
    """A standard shape for testing: (echoes=2, slices=4, rows=3, cols=3)."""
    return (2, 4, 3, 3)


@pytest.fixture
def sample_data(sample_shape):
    """Create sample uint16 data matching sample_shape."""
    np.random.seed(42)
    return np.random.randint(1, 1000, size=sample_shape, dtype=np.uint16)
