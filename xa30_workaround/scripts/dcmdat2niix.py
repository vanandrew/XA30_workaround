#!/usr/bin/env python3
import sys
import json
import shutil
from pathlib import Path
import argparse
import numpy as np
from nibabel.nifti1 import Nifti1Image
import os
import pydicom
from xa30_workaround.dicom import dicom2nifti
from xa30_workaround.dat import dat_to_array


def normalize(data):
    """Normalize the data to be between 0 and 1."""
    return (data - np.min(data)) / (np.max(data) - np.min(data))


def dir_path(path: str) -> Path | None:
    """Validate that a string is a path to a directory."""
    if not path or path is None:
        return None
    elif os.path.isdir(path):
        return Path(path)
    else:
        raise argparse.ArgumentTypeError(f"Directory not found: {path}")


def main():
    parser = argparse.ArgumentParser(description="Convert DICOM and .dat to NIFTI", add_help=False)
    parser.add_argument("-h", "--help", action="store_true")
    parser.add_argument(
        "--dat-dir",
        help="Directory containing DAT files. If not specified, look in the same directory as DICOM files by default. Note that each dat file should have, in the filename, the same Series Instance UID as the DICOM file it is associated with.",
        type=dir_path,
        dest="dat_dir",
        default="",
    )

    # parse arguments
    args, other_args = parser.parse_known_args()

    # get help
    if args.help:
        print("Modified version of dcm2niix that can convert .dat files to NIFTI.")
        print("You should put the .dat files next to the associated DICOM files.")
        print("Or run with `--dat-dir=DATDIR` to look for .dat files in another location.")
        print("Below is the original dcm2niix help:\n")
        dicom2nifti("-h")
        sys.exit(0)

    # we need verbose output to get the dicom location
    if "-v" not in other_args:
        idx = len(other_args) - 1
        other_args.insert(idx, "1")
        other_args.insert(idx, "-v")
    else:
        raise ValueError("Turn off verbose output (-v) as this conflicts with this script.")

    # dicom dir
    if "-o" in other_args:
        # get the index of the -o argument
        o_index = other_args.index("-o")
        # get the output directory
        output_dir = Path(other_args[o_index + 1])
        output_dir.mkdir(parents=True, exist_ok=True)

    # run dcm2niix
    dicoms_nii_map = dicom2nifti(*other_args)

    # loop over each nifti file
    for nifti in dicoms_nii_map:
        # get the associated dicom file
        dicom = dicoms_nii_map[nifti]

        # search for alTE tag in dicom file header (this is not a DICOM tag so we need to search by text)
        TEs = None
        with open(dicom, "rb") as f:
            # search for alTE and get the 8 next lines after
            lines = f.readlines()
            for i, line in enumerate(lines):
                try:
                    line = line.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if "alTE" in line:
                    TEs = np.array(
                        [float(l.decode("utf-8").strip().split("= \t")[1]) / 1e6 for l in lines[i + 1 : i + 9]]
                    )
                    # only grab valid TEs
                    diff = TEs[1:] - TEs[0:-1]
                    TEs = np.insert(TEs[1:][diff > 0], 0, TEs[0])
                    break
        
        # if TEs is None, then we could not find the alTE tag and should raise an error
        if TEs is None:
            raise ValueError(f"Could not find alTE tag in {dicom}.")

        # load the json file of the nifti
        nifti_json = Path(nifti).with_suffix(".json")
        if not nifti_json.exists():
            raise ValueError(f"Could not find json file {nifti_json}.")
        with open(nifti_json, "r") as f:
            metadata = json.load(f)

        # load the nifti file
        nifti_img_path = Path(nifti).with_suffix(".nii")
        suffix = ".nii"
        if not nifti_img_path.exists():
            nifti_img_path = Path(nifti).with_suffix(".nii.gz")
            suffix = ".nii.gz"
            if not nifti_img_path.exists():
                raise ValueError(f"Could not find nifti file {nifti_img_path}.")
        nifti_img = Nifti1Image.load(nifti_img_path)

        # get the shape of the nifti file
        # we want the first dimension to me the number of echos
        # the next three dimensions should be the volume
        # we want to ignore the number of time points
        shape = nifti_img.shape
        rshape = list(shape[::-1])
        if len(rshape) <= 3:
            # it would appear there is only one time point
            # prepend the number of echos to the array
            rshape.insert(0, TEs.shape[0])
        else:
            # it looks like the first dimension is the number of time points
            # replace time with number of TEs
            rshape[0] = TEs.shape[0]

        # now search for .dat files
        if args.dat_dir is None:
            # look for .dat files that neighbor the exemplar dicom file
            dat_files = list(dicom.parent.glob("*.dat"))
        else:
            # look for .dat files in the specified directory
            # find dat files that match the Series Instance UID of the dicom

            # extract Series Instance UID of this dicom file
            # should look something like
            # 1.3.12.2.1107.5.2.43.166158.2023072109355378899049069.0.0.0
            # strip off the last six characters, the .0.0.0 part
            # should then look something like
            # 1.3.12.2.1107.5.2.43.166158.2023072109355378899049069
            dicom_sid = pydicom.dcmread(dicom)[0x0020, 0x000E].value[:-6]
            print(dicom_sid)

            # look for .dat files in dat_dir whose name contains the sid
            # skip hidden files starting with a .
            dat_files = list(args.dat_dir.glob(f"[!.]*{dicom_sid}*.dat"))

        # if no .dat files were found, then skip this nifti
        if len(dat_files) == 0:
            print(f"Could not find any .dat files associated with {dicom}.")
            continue

        # convert these files to a numpy array
        print(f"Found {len(dat_files)} .dat files associated with {dicom}.")
        print("Converting .dat files to nifti...")
        data_array = dat_to_array(dat_files, rshape)
        
        # check if number of frames in nifti matches number of frames in .dat files
        if len(shape) <= 3:
            # There is only one frame (time point) in the nifti.
            if data_array.shape[-1] > 1:
                raise ValueError(f"There is one frame in nifti but {data_array.shape[-1]} frames in the .dat files.")
            data_array = np.squeeze(data_array)
        else:
            if data_array.shape[-1] != shape[-1]:
                raise ValueError(f"The number of frames in the .dat files, {data_array.shape[-1]} does not match the number of frames in the nifti, {shape[-1]}.")

        # do first echo, first frame sanity check
        if len(shape) <= 3:
            # There is only one frame (time point).
            if not np.all(np.isclose(normalize(data_array[..., 0].astype("f8")), normalize(nifti_img.dataobj))):
                raise ValueError(
                    "Sanity check failed. The first echo, first frame of the .dat files does not match the nifti."
                )
        else:
            # Compare the first frames.
            if not np.all(np.isclose(normalize(data_array[..., 0, 0].astype("f8")), normalize(nifti_img.dataobj[..., 0]))):
                raise ValueError(
                    "Sanity check failed. The first echo, first frame of the .dat files does not match the nifti."
                )

        # loop over each echo skipping the first one
        # only renaming if neccessary
        print("Saving nifti files...")
        nifti = Path(nifti)
        echo_prefix = "e"
        for i, t in enumerate(TEs):
            if i == 0:
                # check if e1 is in the filename
                if "e1" not in nifti.name:
                    # skip if echo1 is in filename
                    if "echo1" in nifti.name:
                        echo_prefix = "echo"
                        continue
                    # if not, then add it to the nifti name and rename the file
                    orig_img_path = nifti_img_path
                    orig_json_path = nifti_json
                    if "_ph" in nifti.name:
                        nifti = Path(str(nifti).replace("_ph", "_e1_ph"))
                    else:
                        nifti = Path(str(nifti) + "_e1")
                    nifti_img_path = nifti.with_suffix(suffix)
                    nifti_json = nifti.with_suffix(".json")
                    shutil.move(orig_img_path, nifti_img_path)
                    shutil.move(orig_json_path, nifti_json)
                # TODO: remove later if fixed
                # resave the phase image with the dat data
                if "_ph" in nifti.name:
                    if len(shape) <= 3:
                        # there is only one frame (time point)
                        Nifti1Image(data_array[..., 0], nifti_img.affine, nifti_img.header).to_filename(
                            nifti_img_path
                        )
                    else:
                        # save all frames
                        Nifti1Image(data_array[..., 0, :], nifti_img.affine, nifti_img.header).to_filename(
                            nifti_img_path
                        )
                continue
            # substitute the echo in output_filename
            output_base = Path(str(nifti).replace(f"{echo_prefix}1", f"{echo_prefix}{i + 1}"))
            # copy the metadata
            metadata_copy = metadata.copy()
            # replace the echo time
            metadata_copy["EchoTime"] = t
            # replace the ConversionSoftware
            metadata_copy["ConversionSoftware"] = "dcmdat2niix"
            # save the nifti file
            output_path = output_base.with_suffix(suffix)
            if len(shape) <= 3:
                # there is only one frame (time point)
                Nifti1Image(data_array[..., i], nifti_img.affine, nifti_img.header).to_filename(output_path)
            else:
                # save all frames
                Nifti1Image(data_array[..., i, :], nifti_img.affine, nifti_img.header).to_filename(output_path)
            # save the json file
            output_json = output_path.with_suffix(".json")
            with open(output_json, "w") as f:
                json.dump(metadata_copy, f, indent=4)
    print("Done.")


if __name__ == "__main__":
    main()
