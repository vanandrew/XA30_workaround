# specify the path to the folder you want to copy from
$DatPath = "C:\ProgramData\Siemens\Numaris\SimMeasData\NORDIC"

# desintation folder
$DestinationPath = "Microsoft.PowerShell.Core\FileSystem::\\Server\Data"

# read in PatientID from stdin
$PatientID = Read-Host "Enter PatientID: "

# count number of files matching PatientID in DatPath
$NumFiles = (Get-ChildItem -Path $DatPath\*.dat -Filter $PatientID*).Count

# if no files found, exit
if ($NumFiles -eq 0) {
  Write-Host "No files found matching PatientID $PatientID" -ForegroundColor Red
  exit
}

# if files found then tell the user how many we found
Write-Host "Found $NumFiles files matching PatientID $PatientID" -ForegroundColor Green

# now ask user if they want to copy these files
$CopyFiles = Read-Host "Copy dat files? (y/N): "

# if y, Y, yes, or Yes then copy files
if ($CopyFiles -eq "y" -or $CopyFiles -eq "Y" -or $CopyFiles -eq "yes" -or $CopyFiles -eq "Yes") {
  Write-Host "Copying files..." -ForegroundColor Green
  # copy all dat files in folder
  Copy-Item -Path $DatPath\*.dat -Destination $DestinationPath -Filter $PatientID* -Verbose
} else {
  Write-Host "Not copying files" -ForegroundColor Red
  exit
}
