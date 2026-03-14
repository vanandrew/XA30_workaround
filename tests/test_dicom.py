import subprocess
from unittest.mock import patch
import pytest

# dicom.py checks for dcm2niix at import time and exits if not found.
# Patch subprocess.run to prevent that side effect during testing.
with patch("subprocess.run"):
    from xa30_workaround.dicom import execute, dicom2nifti


class TestExecute:
    def test_yields_stdout_lines(self):
        """execute() should yield each line of stdout."""
        lines = list(execute(["echo", "hello\nworld"]))
        assert any("hello" in line for line in lines)

    def test_raises_on_nonzero_exit(self):
        """execute() should raise CalledProcessError on failure."""
        with pytest.raises(subprocess.CalledProcessError):
            list(execute(["false"]))


class TestDicom2Nifti:
    def test_parses_converting_line(self):
        """dicom2nifti should parse 'Converting' and 'Convert...DICOM as' lines."""
        fake_output = [
            "Converting /data/scan/file.dcm\n",
            "Convert 1 DICOM as /output/scan_e1 (64x64x40x100)\n",
        ]

        with patch("xa30_workaround.dicom.execute", return_value=iter(fake_output)):
            result = dicom2nifti("-z", "y", "/data/scan")

        assert "/output/scan_e1" in result
        assert str(result["/output/scan_e1"]) == "/data/scan/file.dcm"

    def test_skips_verbose_lines(self):
        """Lines with 'Patient Position', 'orient', 'acq', 'DICOM file:' should be skipped."""
        fake_output = [
            "Patient Position: HFS\n",
            "patient position is HFS\n",
            "orient something\n",
            "acq parameters\n",
            "DICOM file: /data/file.dcm\n",
            "Converting /data/scan/file.dcm\n",
            "Convert 1 DICOM as /output/result (64x64x40)\n",
        ]

        with patch("xa30_workaround.dicom.execute", return_value=iter(fake_output)):
            result = dicom2nifti("/data/scan")

        assert len(result) == 1

    def test_multiple_conversions(self):
        """Should handle multiple DICOM-to-NIFTI conversions."""
        fake_output = [
            "Converting /data/scan1/file1.dcm\n",
            "Convert 1 DICOM as /output/scan1_e1 (64x64x40)\n",
            "Converting /data/scan2/file2.dcm\n",
            "Convert 2 DICOM as /output/scan2_e1 (64x64x40)\n",
        ]

        with patch("xa30_workaround.dicom.execute", return_value=iter(fake_output)):
            result = dicom2nifti("/data")

        assert len(result) == 2
        assert "/output/scan1_e1" in result
        assert "/output/scan2_e1" in result

    def test_empty_output(self):
        """No conversions should return empty dict."""
        with patch("xa30_workaround.dicom.execute", return_value=iter([])):
            result = dicom2nifti("/data")
        assert result == {}
