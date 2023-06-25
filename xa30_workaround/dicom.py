import sys
import subprocess
from pathlib import Path

# test if dcm2niix is installed
try:
    subprocess.run(["dcm2niix", "-h"], stdout=subprocess.DEVNULL, check=True)
except subprocess.CalledProcessError:
    print("dcm2niix not installed. Please install dcm2niix and try again.")
    sys.exit(1)


def execute(cmd):
    popen = subprocess.Popen(cmd, stdout=subprocess.PIPE, universal_newlines=True)
    for stdout_line in iter(popen.stdout.readline, ""):
        yield stdout_line
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, cmd)


def dicom2nifti(*args):
    dcm2niix_cmd = ["dcm2niix", *args]
    dicom_path = None
    dicoms_nii_map = {}
    i = 0
    for line in execute(dcm2niix_cmd):
        # skip non-essential verbose lines
        if "Patient Position" in line:
            continue
        if "patient position" in line or "orient" in line or "acq" in line:
            continue
        if "DICOM file: " in line:
            continue
        print(line, end="")
        if "Converting " in line:
            # add dicom path
            dicom_path = Path(line.split("Converting ")[1].strip())
        if line.startswith("Convert ") and "DICOM as " in line:
            # get the nifti name
            nifti_name = line.split(" DICOM as ")[1].split(" (")[0]
            dicoms_nii_map[nifti_name] = dicom_path
            # increment the image index
            i += 1
    return dicoms_nii_map
