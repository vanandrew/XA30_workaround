# XA30_workaround

Workaround scripts for XA30.

This repo contains some scripts to get around limitations of the SIEMENS XA30A MRI scanner.

When running Multi-echo sequences with many measurements (like the BOLD NORDIC sequence), XA30A cannot handle the
load. The cause seems to be related to the second reconstruction pipeline that users do not have access to.

> [!NOTE]
> The log output in UTraceSrv.utr suggests that this second pipeline begins 
> right after the usual ICE reconstruction that ends with ImageSend. This second 
> pipeline seems to be the one that writes out the DICOMs because the log file showed 
> function names like “DICOM backend writer”. This is the suspect!​

Our solution for this was to not send images to the DICOM backend writer except the very first echo, sending the rest
of the echoes (including the first one for comparison purposes) to be saved as binary files that carry unsigned
16-bit integer matrices. These are 4D matrices of size #columns x #rows x #slices x #echoes, and basically contain 1
measurement instance (magnitude or phase)​.

> [!NOTE]
> The solution is embedded into the ICE program (.ipr file) for the CMRR BOLD sequence,
> and gets activated only if the protocol has “BOLD_NORDIC” anywhere in its name.

To copy the extra binary files written by the ICE program, you can use the `dat_copier.ps1` powershell script provided.
The user runs it and enters the patient name to initiate the process.

This repo also contains files for converting the `.dat` files paired with the `.dcm` files to `.nii` files. It functions
as a drop-in replacement for `dcm2niix`.

## Installation

This repo contains two sets of files:

1. The first is a script located under `host_scripts` and is intended to be installed on your scanner console. This
script is called `dat_coper.ps1` and is intended to be run on the scanner console. It copies `.dat` files from the
scanner to a location of your choice.

2. The second contains `dcmdat2niix` script, which takes in `.dat` files alongside `.dcm` files and converts them to
`.nii` files.

### Installation instructions for `host_scripts`

STEPS FOR INSTALLING `dat_copier.ps1`.

### Installation instructions for `dcmdat2niix`

First, ensure that `dcm2niix` is installed and on your path.

> [!NOTE] 
> `dcm2niix` is available from [here](https://github.com/rordenlab/dcm2niix).
> Version v1.0.20220720 or later is required.

To install `dcmdat2niix`, clone this repo and install using `pip`:

```bash
# install using pip and local path to repo
git clone https://github.com/vanandrew/XA30_workaround.git
cd XA30_workaround
pip install .
```

If the install is successful, you should see `dcmdat2niix` in your path. You can check this by running:

```bash
dcmdat2niix -h
```

## Usage

ADD USAGE INSTRUCTIONS HERE
