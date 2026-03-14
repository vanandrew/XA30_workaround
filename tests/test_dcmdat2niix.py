import json
import numpy as np
import nibabel as nib
import pytest
import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock  # noqa: F401 - used for import-time patching

# Patch dcm2niix check that runs at dicom.py import time
with patch("subprocess.run"):
    from xa30_workaround.scripts.dcmdat2niix import normalize, match_orientation, dir_path, main


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


def _make_fake_dicom(path, te_values):
    """Create a fake DICOM-like binary file with an alTE section."""
    lines = [b"some binary header data\n"]
    lines.append(b"alTE\n")
    for te in te_values:
        lines.append(f"= \t{te}\n".encode("utf-8"))
    # pad remaining lines so we always have 8 lines after alTE
    while len(lines) < 2 + 8:
        lines.append(b"= \t0\n")
    lines.append(b"more binary data\n")
    path.write_bytes(b"".join(lines))


def _make_nifti(path, data):
    """Save a minimal NIFTI file."""
    img = nib.Nifti1Image(data.astype(np.float32), np.eye(4))
    img.to_filename(str(path))


def _make_dat_file(path, data):
    """Write a .dat file with uint16 data."""
    data.astype(np.uint16).tofile(str(path))


@pytest.fixture
def main_workspace(tmp_path):
    """Set up a workspace for testing main() with all required files."""
    dicom_dir = tmp_path / "dicom"
    dicom_dir.mkdir()

    # Create nifti data: 3D volume (4x5x6)
    rng = np.random.RandomState(42)
    nifti_data = rng.randint(10, 1000, size=(4, 5, 6), dtype=np.uint16).astype(np.float32)

    # Create the nifti file
    nifti_stem = str(dicom_dir / "test_scan")
    _make_nifti(nifti_stem + ".nii", nifti_data)

    # Create matching JSON metadata
    metadata = {
        "EchoTime": 0.02,
        "ConversionSoftware": "dcm2niix",
        "ImageTypeText": ["ORIGINAL", "PRIMARY", "TE1", "ND"],
    }
    with open(nifti_stem + ".json", "w") as f:
        json.dump(metadata, f)

    # Create fake DICOM with 2 echo times (in microseconds)
    dicom_path = dicom_dir / "test.dcm"
    # TEs: 20000 us and 40000 us -> 0.02 and 0.04 ms after /1e6
    _make_fake_dicom(dicom_path, [20000, 40000, 0, 0, 0, 0, 0, 0])

    # Create .dat files that match the nifti data
    # dat_to_array expects shape (echoes, slices, rows, cols) -> rshape
    # For 2 echoes and a 4x5x6 nifti, rshape is [2, 6, 5, 4]
    # dat_to_array does interleave reorder + flip + moveaxis
    # We need to create dat data that, after processing, matches the nifti.
    # The simplest approach: create dat data and let match_orientation fix it.
    dat_data = rng.randint(10, 1000, size=(2 * 6 * 5 * 4,), dtype=np.uint16)
    dat_file = dicom_dir / "frame_001.dat"
    _make_dat_file(dat_file, dat_data)

    return {
        "tmp_path": tmp_path,
        "dicom_dir": dicom_dir,
        "nifti_stem": nifti_stem,
        "dicom_path": dicom_path,
        "dat_file": dat_file,
        "nifti_data": nifti_data,
        "metadata": metadata,
    }


class TestMain:
    """Tests for the main() entry point."""

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    @patch("xa30_workaround.scripts.dcmdat2niix.match_orientation")
    def test_basic_run(self, mock_orient, mock_dcm2nii, main_workspace):
        """main() should produce echo NIFTI files for each TE."""
        ws = main_workspace
        # dicom2nifti returns map of nifti stem -> dicom path
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}

        # match_orientation just passes data through
        def passthrough(dat, nifti_data):
            return dat

        mock_orient.side_effect = passthrough

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            main()

        # Should have created echo 2 nifti + json
        e2_nii = Path(ws["nifti_stem"].replace("test_scan", "test_scan_e2") + ".nii")
        e2_json = Path(ws["nifti_stem"].replace("test_scan", "test_scan_e2") + ".json")
        assert e2_nii.exists()
        assert e2_json.exists()

        # Check metadata was updated
        with open(e2_json) as f:
            meta = json.load(f)
        assert meta["EchoTime"] == 0.04
        assert meta["ConversionSoftware"] == "dcmdat2niix"
        assert "TE2" in meta["ImageTypeText"]

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    @patch("xa30_workaround.scripts.dcmdat2niix.match_orientation")
    def test_renames_first_echo(self, mock_orient, mock_dcm2nii, main_workspace):
        """First echo should be renamed to include _e1 if not present."""
        ws = main_workspace
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}
        mock_orient.side_effect = lambda dat, nifti_data: dat

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            main()

        # Original file should be renamed to _e1
        e1_nii = Path(ws["nifti_stem"].replace("test_scan", "test_scan_e1") + ".nii")
        assert e1_nii.exists()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    def test_no_dat_files_skips(self, mock_dcm2nii, main_workspace, capsys):
        """If no .dat files found, the nifti should be skipped."""
        ws = main_workspace
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}

        # Remove the .dat file
        ws["dat_file"].unlink()

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            main()

        captured = capsys.readouterr()
        assert "Could not find any .dat files" in captured.out

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    def test_missing_alte_raises(self, mock_dcm2nii, main_workspace):
        """Should raise ValueError if DICOM has no alTE tag."""
        ws = main_workspace
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}

        # Overwrite dicom with no alTE
        ws["dicom_path"].write_bytes(b"no echo time info here\n")

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            with pytest.raises(ValueError, match="Could not find alTE tag"):
                main()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    def test_missing_json_raises(self, mock_dcm2nii, main_workspace):
        """Should raise ValueError if JSON sidecar is missing."""
        ws = main_workspace
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}

        # Remove the JSON file
        Path(ws["nifti_stem"] + ".json").unlink()

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            with pytest.raises(ValueError, match="Could not find json file"):
                main()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    def test_missing_nifti_raises(self, mock_dcm2nii, main_workspace):
        """Should raise ValueError if NIFTI image file is missing."""
        ws = main_workspace
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}

        # Remove the nifti file
        Path(ws["nifti_stem"] + ".nii").unlink()

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            with pytest.raises(ValueError, match="Could not find nifti file"):
                main()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    def test_verbose_flag_conflict_raises(self, mock_dcm2nii, main_workspace):
        """Should raise ValueError if -v is already in args."""
        ws = main_workspace

        with patch("sys.argv", ["dcmdat2niix", "-v", "1", str(ws["dicom_dir"])]):
            with pytest.raises(ValueError, match="Turn off verbose output"):
                main()

    def test_help_flag_exits(self, capsys):
        """--help should print help and exit."""
        with patch("sys.argv", ["dcmdat2niix", "--help"]):
            with patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti"):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "dcmdat2niix Version" in captured.out

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    @patch("xa30_workaround.scripts.dcmdat2niix.match_orientation")
    def test_output_dir_created(self, mock_orient, mock_dcm2nii, main_workspace):
        """If -o is specified, the output directory should be created."""
        ws = main_workspace
        out_dir = ws["tmp_path"] / "output" / "nested"
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}
        mock_orient.side_effect = lambda dat, nifti_data: dat

        with patch("sys.argv", ["dcmdat2niix", "-o", str(out_dir), str(ws["dicom_dir"])]):
            main()

        assert out_dir.exists()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    @patch("xa30_workaround.scripts.dcmdat2niix.match_orientation")
    def test_echo_prefix_for_complex_images(self, mock_orient, mock_dcm2nii, tmp_path):
        """Phase images (_ph) should be handled with echo prefix insertion."""
        dicom_dir = tmp_path / "dcm"
        dicom_dir.mkdir()

        rng = np.random.RandomState(42)
        nifti_data = rng.randint(10, 1000, size=(4, 5, 6), dtype=np.uint16).astype(np.float32)
        nifti_stem = str(dicom_dir / "scan_ph")
        _make_nifti(nifti_stem + ".nii", nifti_data)

        metadata = {
            "EchoTime": 0.02,
            "ConversionSoftware": "dcm2niix",
            "ImageTypeText": ["ORIGINAL", "PRIMARY", "TE1", "ND"],
        }
        with open(nifti_stem + ".json", "w") as f:
            json.dump(metadata, f)

        dicom_path = dicom_dir / "test.dcm"
        _make_fake_dicom(dicom_path, [20000, 40000, 0, 0, 0, 0, 0, 0])

        dat_data = rng.randint(10, 1000, size=(2 * 6 * 5 * 4,), dtype=np.uint16)
        (dicom_dir / "frame_001.dat").write_bytes(dat_data.tobytes())

        mock_dcm2nii.return_value = {nifti_stem: dicom_path}
        mock_orient.side_effect = lambda dat, nifti_data: dat

        with patch("sys.argv", ["dcmdat2niix", str(dicom_dir)]):
            main()

        # Phase image should have _e1_ph naming
        e1_ph = dicom_dir / "scan_e1_ph.nii"
        assert e1_ph.exists()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    @patch("xa30_workaround.scripts.dcmdat2niix.match_orientation")
    def test_multiframe_nifti(self, mock_orient, mock_dcm2nii, tmp_path):
        """4D nifti (with time points) should process correctly."""
        dicom_dir = tmp_path / "dicom"
        dicom_dir.mkdir()

        rng = np.random.RandomState(42)
        # 4D: (4, 5, 6, 3) -> 3 time points
        nifti_data = rng.randint(10, 1000, size=(4, 5, 6, 3), dtype=np.uint16).astype(np.float32)
        nifti_stem = str(dicom_dir / "test_scan")
        _make_nifti(nifti_stem + ".nii", nifti_data)

        metadata = {
            "EchoTime": 0.02,
            "ConversionSoftware": "dcm2niix",
            "ImageTypeText": ["ORIGINAL", "PRIMARY", "TE1", "ND"],
        }
        with open(nifti_stem + ".json", "w") as f:
            json.dump(metadata, f)

        dicom_path = dicom_dir / "test.dcm"
        _make_fake_dicom(dicom_path, [20000, 40000, 0, 0, 0, 0, 0, 0])

        # Need 3 dat files (one per frame), each with shape (2, 6, 5, 4)
        for i in range(3):
            dat_data = rng.randint(10, 1000, size=(2 * 6 * 5 * 4,), dtype=np.uint16)
            (dicom_dir / f"frame_{i + 1:03d}.dat").write_bytes(dat_data.tobytes())

        mock_dcm2nii.return_value = {nifti_stem: dicom_path}
        mock_orient.side_effect = lambda dat, nifti_data: dat

        with patch("sys.argv", ["dcmdat2niix", str(dicom_dir)]):
            main()

        # Should create echo 2 file
        e2_nii = dicom_dir / "test_scan_e2.nii"
        assert e2_nii.exists()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    @patch("xa30_workaround.scripts.dcmdat2niix.match_orientation")
    def test_dat_dir_option(self, mock_orient, mock_dcm2nii, tmp_path):
        """--dat-dir should search for dat files in the specified directory."""
        dicom_dir = tmp_path / "dicom"
        dicom_dir.mkdir()
        dat_dir = tmp_path / "dat_files"
        dat_dir.mkdir()

        rng = np.random.RandomState(42)
        nifti_data = rng.randint(10, 1000, size=(4, 5, 6), dtype=np.uint16).astype(np.float32)
        nifti_stem = str(dicom_dir / "test_scan")
        _make_nifti(nifti_stem + ".nii", nifti_data)

        metadata = {
            "EchoTime": 0.02,
            "ConversionSoftware": "dcm2niix",
            "ImageTypeText": ["ORIGINAL", "PRIMARY", "TE1", "ND"],
        }
        with open(nifti_stem + ".json", "w") as f:
            json.dump(metadata, f)

        # Create a real DICOM file with Series Instance UID and alTE
        dicom_path = dicom_dir / "test.dcm"

        # Build a minimal DICOM with pydicom
        import pydicom
        from pydicom.dataset import Dataset, FileDataset

        ds = FileDataset(str(dicom_path), Dataset(), preamble=b"\x00" * 128)
        ds.SeriesInstanceUID = "1.3.12.2.1107.5.2.43.166158.2023072109355378899049069.0.0.0"
        ds.is_little_endian = True
        ds.is_implicit_VR = False
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
        ds.file_meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
        ds.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
        ds.save_as(str(dicom_path))

        # Now append alTE data to the dicom file (the main() reads it as binary)
        with open(dicom_path, "ab") as f:
            f.write(b"\nalTE\n")
            for te in [20000, 40000, 0, 0, 0, 0, 0, 0]:
                f.write(f"= \t{te}\n".encode("utf-8"))

        # Create dat files in dat_dir with the SID in the name (minus last 6 chars)
        sid_prefix = "1.3.12.2.1107.5.2.43.166158.2023072109355378899049069"
        dat_data = rng.randint(10, 1000, size=(2 * 6 * 5 * 4,), dtype=np.uint16)
        (dat_dir / f"img_{sid_prefix}_001.dat").write_bytes(dat_data.tobytes())

        mock_dcm2nii.return_value = {nifti_stem: dicom_path}
        mock_orient.side_effect = lambda dat, nifti_data: dat

        with patch("sys.argv", ["dcmdat2niix", f"--dat-dir={str(dat_dir)}", str(dicom_dir)]):
            main()

        # Should find the dat file and produce output
        e2_nii = dicom_dir / "test_scan_e2.nii"
        assert e2_nii.exists()

    @patch("xa30_workaround.scripts.dcmdat2niix.dicom2nifti")
    def test_frame_count_mismatch_raises(self, mock_dcm2nii, main_workspace):
        """Should raise if dat has more frames than nifti (single frame nifti)."""
        ws = main_workspace
        mock_dcm2nii.return_value = {ws["nifti_stem"]: ws["dicom_path"]}

        # Add a second dat file -> 2 frames but nifti is 3D (1 frame)
        rng = np.random.RandomState(99)
        dat_data = rng.randint(10, 1000, size=(2 * 6 * 5 * 4,), dtype=np.uint16)
        (ws["dicom_dir"] / "frame_002.dat").write_bytes(dat_data.tobytes())

        with patch("sys.argv", ["dcmdat2niix", str(ws["dicom_dir"])]):
            with pytest.raises(ValueError, match="one frame in nifti"):
                main()
