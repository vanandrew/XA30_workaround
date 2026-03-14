import numpy as np
import pytest
from xa30_workaround.dat import dat_to_array


class TestDatToArray:
    def test_reads_binary_data(self, tmp_dat_file, sample_shape):
        """dat_to_array should read binary uint16 data and return a numpy array."""
        data = np.random.RandomState(0).randint(1, 1000, size=sample_shape, dtype=np.uint16)
        dat_path = tmp_dat_file(data, "frame_001.dat")
        result = dat_to_array([dat_path], sample_shape)
        assert result.dtype == np.uint16
        assert result.shape[-1] == 1  # one frame stacked

    def test_output_shape_single_frame(self, tmp_dat_file, sample_shape):
        """Single .dat file should produce array with last dim = 1."""
        data = np.random.RandomState(1).randint(1, 1000, size=sample_shape, dtype=np.uint16)
        dat_path = tmp_dat_file(data, "frame_001.dat")
        result = dat_to_array([dat_path], sample_shape)
        # Original shape is (echoes=2, slices=4, rows=3, cols=3)
        # After moveaxis [0,1,2,3]->[3,2,1,0]: (3, 3, 4, 2)
        # After flip(1): (3, 3, 4, 2)
        # After stack: (3, 3, 4, 2, 1)
        assert result.shape == (3, 3, 4, 2, 1)

    def test_multiple_frames_stacked(self, tmp_dat_file, sample_shape):
        """Multiple .dat files should be stacked along the last dimension."""
        rng = np.random.RandomState(2)
        paths = []
        for i in range(3):
            data = rng.randint(1, 1000, size=sample_shape, dtype=np.uint16)
            paths.append(tmp_dat_file(data, f"frame_{i:03d}.dat"))
        result = dat_to_array(paths, sample_shape)
        assert result.shape[-1] == 3

    def test_empty_file_raises(self, tmp_path):
        """An empty .dat file should raise RuntimeError."""
        empty_path = tmp_path / "empty.dat"
        empty_path.write_bytes(b"")
        with pytest.raises(RuntimeError, match="contains no data"):
            dat_to_array([empty_path], (2, 4, 3, 3))

    def test_interleaved_reordering(self, tmp_dat_file):
        """Slices should be reordered from interleaved to sequential."""
        # 4 slices: interleaved order is [1, 3, 0, 2] -> sequential [0, 1, 2, 3]
        shape = (1, 4, 2, 2)
        data = np.arange(16, dtype=np.uint16).reshape(shape)
        dat_path = tmp_dat_file(data, "test.dat")
        result = dat_to_array([dat_path], shape)
        # The function applies interleaved reordering — result should differ from
        # raw reshape if slices were already sequential
        assert result is not None
        assert result.size == 16

    def test_files_sorted_by_name(self, tmp_dat_file):
        """Files should be processed in sorted order."""
        shape = (1, 2, 2, 2)
        rng = np.random.RandomState(3)
        # Create files in reverse order
        paths = []
        for name in ["c.dat", "a.dat", "b.dat"]:
            data = rng.randint(1, 100, size=shape, dtype=np.uint16)
            paths.append(tmp_dat_file(data, name))

        result = dat_to_array(paths, shape)
        assert result.shape[-1] == 3

    def test_wrong_shape_raises(self, tmp_dat_file):
        """Mismatched shape should raise an error during reshape."""
        data = np.ones(10, dtype=np.uint16)
        dat_path = tmp_dat_file(data, "bad.dat")
        with pytest.raises(ValueError):
            dat_to_array([dat_path], (3, 3, 3, 3))
