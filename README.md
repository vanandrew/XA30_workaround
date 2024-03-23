# XA30_workaround

This repo contains some scripts to get around the limitations of the SIEMENS XA30A image database implementation,
specifically system crashes or dramatically degraded responsivity when acquiring multi-echo BOLD.

When running multi-echo sequences with many measurements (like the CMRR BOLD sequence), the XA30A image database cannot
handle the load. 

> [!NOTE]
> The log output in UTraceSrv.utr suggests that the problem arises right after the usual ICE reconstruction that ends
> with ImageSend, during which DICOMs are written into the image database, because the log file showed function names
> like “DICOM backend writer”.

Our solution for this was to send the reconstructed images for only the very first echo to the DICOM backend writer,
with the rest of the reconstructed echoes (including the first echo for comparison purposes) written directly to a
binary file that contains unsigned 16-bit integers. These binary files are of size #columns x #rows x #slices x #echoes,
and contain just the reconstructed (image-domain) data for 1 measurement instance (either magnitude or phase)​.

> [!NOTE]
> The solution is embedded into a modified version of the ICE program (.ipr file) for the CMRR BOLD sequence,
> and gets activated only if the scan has “MBME_DcmOnlyE1” anywhere in its name.

To copy the extra binary files written by the ICE program, you can use the `dat_copier.ps1` PowerShell script provided.
The user runs it and enters the patient ID to initiate the process.

This repo also contains files for converting the generated binary `.dat` files (not to be confused with the raw k-space
.dat files) into `.nii` files. It uses `dcm2niix` and the header information available in the existing `.dcm` files
(corresponding to the first echoes) to construct a NIFTI version of all the echoes.

## Installation

This repo contains two sets of files:

1. The first is a PowerShell script located under `host_scripts` and is intended to be installed on your scanner
console. This script is called `dat_copier.ps1` and is intended to be run on the scanner console when the session is
completed. It copies `.dat` files from the scanner to a location of your choice.

2. The second contains the `dcmdat2niix` script, which takes in `.dat` files alongside `.dcm` files and converts them
to `.nii` files.

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

### Data organization

Once you've copied your data off the scanner, you should have a collection of `.dcm` and `.dat` files for your data.
Each `.dat` file is named with a unique series instance UID. You can match this UID to the corresponding `.dcm` file by
checking the header of one of the `.dcm` files for a particular series.

After identifying the corresponding series, place the correponding `.dat` files in the same folder. `dcmdat2niix` will
auto detect the `.dat` files and use the corresponding `.dcm` files to construct the NIFTI files.

### Running `dcmdat2niix`

You can use `dcmdat2niix` in the same way you would use `dcm2niix`. For example, if you invoked:

```bash
dcm2niix -z y -f %p_%t_%s -o /path/output /path/to/dicom/folder
```

you can invoke `dcmdat2niix` in the same way:

```bash
dcmdat2niix -z y -f %p_%t_%s -o /path/output /path/to/dicom/folder
```

## Current limitations

1. `dcmdat2niix` currently only supports interleaved slices.
2. Since `dcmdat2niix` parses the verbose output of `dcm2niix`, the `-v` flag is forced on. Manually specifying `-v`
on `dcmdat2niix` will result in an error.
3. Echo detection is currently done by looking at `e#` or `echo#` (e.g. `e1` or `echo1`) in the filename. If you choose
to use a different naming convention, this script will likely not work :(.
4. Metadata (JSON sidecar) for any subsequent echoes past the 1st echo is copied from the 1st echo. The only metadata
information that is replaced is the `EchoTime` field, which is replaced with the appropriate echo time parameter for
that echo. This is obtained from the `alTE` field in the DICOM header (this is not an actual DICOM tag so it is text
parsed from the DICOM).
