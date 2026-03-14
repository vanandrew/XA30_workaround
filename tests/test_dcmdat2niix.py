import numpy as np
import pytest
import argparse
from pathlib import Path
from unittest.mock import patch  # noqa: F401 - used for import-time patching

# Patch dcm2niix check that runs at dicom.py import time
with patch("subprocess.run"):
    from xa30_workaround.scripts.dcmdat2niix import normalize, match_orientation, dir_path


class TestNormalize:
    def test_range_zero_to_one(self):
        """Normalized data should be in [0, 1]."""
        data = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        result = normalize(data)
        assert np.isclose(result.min(), 0.0)
        assert np.isclose(result.max(), 1.0)

    def test_preserves_relative_order(self):
        """Normalization should preserve relative ordering."""
        data = np.array([1.0, 3.0, 2.0])
        result = normalize(data)
        assert result[1] > result[2] > result[0]

    def test_multidimensional(self):
        """Should work with multi-dimensional arrays."""
        data = np.random.RandomState(0).rand(3, 4, 5) * 100
        result = normalize(data)
        assert np.isclose(result.min(), 0.0)
        assert np.isclose(result.max(), 1.0)

    def test_constant_array(self):
        """Constant array produces NaN (0/0 division)."""
        data = np.array([5.0, 5.0, 5.0])
        result = normalize(data)
        assert np.all(np.isnan(result))


class TestMatchOrientation:
    def _make_data(self, shape_3d=(4, 5, 6)):
        """Create matching dat and nifti data (4D dat with echo, 3D nifti)."""
        rng = np.random.RandomState(42)
        base = rng.rand(*shape_3d).astype(np.float64)
        # dat has echo dimension: shape (4, 5, 6, 1)
        dat = np.expand_dims(base, axis=-1).astype(np.float64)
        nifti = base
        return dat, nifti

    def test_already_matching(self):
        """If orientations match, return data unchanged."""
        dat, nifti = self._make_data()
        result = match_orientation(dat, nifti)
        assert np.array_equal(result, dat)

    def test_flip_axis_0(self):
        """Should detect and correct flip along axis 0."""
        dat, nifti = self._make_data()
        flipped_dat = np.flip(dat, 0)
        result = match_orientation(flipped_dat, nifti)
        assert np.allclose(normalize(result[..., 0]), normalize(nifti))

    def test_flip_axis_1(self):
        """Should detect and correct flip along axis 1."""
        dat, nifti = self._make_data()
        flipped_dat = np.flip(dat, 1)
        result = match_orientation(flipped_dat, nifti)
        assert np.allclose(normalize(result[..., 0]), normalize(nifti))

    def test_flip_axis_2(self):
        """Should detect and correct flip along axis 2."""
        dat, nifti = self._make_data()
        flipped_dat = np.flip(dat, 2)
        result = match_orientation(flipped_dat, nifti)
        assert np.allclose(normalize(result[..., 0]), normalize(nifti))

    def test_flip_two_axes(self):
        """Should detect and correct flip along two axes."""
        dat, nifti = self._make_data()
        flipped_dat = np.flip(dat, (0, 2))
        result = match_orientation(flipped_dat, nifti)
        assert np.allclose(normalize(result[..., 0]), normalize(nifti))

    def test_flip_all_axes(self):
        """Should detect and correct flip along all three axes."""
        dat, nifti = self._make_data()
        flipped_dat = np.flip(dat, (0, 1, 2))
        result = match_orientation(flipped_dat, nifti)
        assert np.allclose(normalize(result[..., 0]), normalize(nifti))

    def test_unrecoverable_mismatch_raises(self):
        """Should raise ValueError if no flip combination works."""
        rng = np.random.RandomState(42)
        dat = rng.rand(4, 5, 6, 1).astype(np.float64)
        nifti = np.random.RandomState(99).rand(4, 5, 6)  # totally different data
        with pytest.raises(ValueError, match="Sanity check failed"):
            match_orientation(dat, nifti)

    def test_5d_dat_with_frames(self):
        """Should work with 5D dat (x, y, z, echoes, frames)."""
        rng = np.random.RandomState(42)
        base = rng.rand(4, 5, 6).astype(np.float64)
        # 5D: shape (4, 5, 6, 2, 3) — 2 echoes, 3 frames
        dat = np.stack([np.stack([base * (e + 1) * (f + 1) for e in range(2)], axis=-1) for f in range(3)], axis=-1)
        nifti = base * 1  # matches first echo (e=0), first frame (f=0) -> base * 1 * 1
        # Add frame dim to nifti to match the indexing in match_orientation
        nifti_with_frame = np.expand_dims(nifti, axis=-1)
        result = match_orientation(dat, nifti_with_frame)
        assert result.shape == dat.shape


class TestDirPath:
    def test_valid_directory(self, tmp_path):
        """Should return a Path for a valid directory."""
        result = dir_path(str(tmp_path))
        assert isinstance(result, Path)
        assert result == tmp_path

    def test_invalid_directory_raises(self):
        """Should raise ArgumentTypeError for non-existent path."""
        with pytest.raises(argparse.ArgumentTypeError, match="Directory not found"):
            dir_path("/nonexistent/path/abc123")

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        assert dir_path("") is None

    def test_none_returns_none(self):
        """None input should return None."""
        assert dir_path(None) is None
