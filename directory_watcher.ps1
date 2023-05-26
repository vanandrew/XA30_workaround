# specify the path to the folder you want to monitor:
$MonitoringPath = "C:\ProgramData\Siemens\Numaris\SimMeasData\NORDIC"
$global:DestinationPath = "Microsoft.PowerShell.Core\FileSystem::\\ARCHLEMUR\Data"
# $MonitoringPath = "/home/vanandrew/Data/test"
# $global:DestinationPath = "/home/vanandrew/Projects/XA30_workaround/shares/data"

# specify which files you want to monitor
$FileFilter = '*.dat'  

# specify whether you want to monitor subfolders as well:
$IncludeSubfolders = $true

# specify the file or folder properties you want to monitor:
$AttributeFilter = [IO.NotifyFilters]::FileName, [IO.NotifyFilters]::LastWrite 

try {
  $watcher = New-Object -TypeName System.IO.FileSystemWatcher -Property @{
    Path                  = $MonitoringPath
    Filter                = $FileFilter
    IncludeSubdirectories = $IncludeSubfolders
    NotifyFilter          = $AttributeFilter
  }

  # define the code that should execute when a change occurs:
  $action = {
    # the code is receiving this to work with:
    
    # change type information:
    $details = $event.SourceEventArgs
    # $Name = $details.Name
    $FullPath = $details.FullPath
    # $OldFullPath = $details.OldFullPath
    # $OldName = $details.OldName
    
    # type of change:
    $ChangeType = $details.ChangeType
    
    # when the change occured:
    $Timestamp = $event.TimeGenerated
    
    # save information to a global variable for testing purposes
    # so you can examine it later
    # MAKE SURE YOU REMOVE THIS IN PRODUCTION!
    # $global:all = $details
    
    # now you can define some action to take based on the
    # details about the change event:
    
    # let's compose a message:
    $text = "{0} was {1} at {2}" -f $FullPath, $ChangeType, $Timestamp
    Write-Host ""
    Write-Host $text -ForegroundColor DarkYellow

    # if the change type was Created, copy the file over to the new directory at $NewPath
    if ($ChangeType -eq 'Created') {
      Write-Host "Copying $FullPath to $DestinationPath" -ForegroundColor DarkYellow
      Copy-Item $FullPath -Destination $DestinationPath
    }
  }

  # subscribe your event handler to all event types that are
  # important to you. Do this as a scriptblock so all returned
  # event handlers can be easily stored in $handlers:
  $handlers = . {
    # Register-ObjectEvent -InputObject $watcher -EventName Changed -Action $action 
    Register-ObjectEvent -InputObject $watcher -EventName Created -Action $action 
    # Register-ObjectEvent -InputObject $watcher -EventName Deleted -Action $action 
    # Register-ObjectEvent -InputObject $watcher -EventName Renamed -Action $action 
  }

  # monitoring starts now:
  $watcher.EnableRaisingEvents = $true

  Write-Host " _____  _               _                    __          __   _       _               "
  Write-Host "|  __ \(_)             | |                   \ \        / /  | |     | |              "
  Write-Host "| |  | |_ _ __ ___  ___| |_ ___  _ __ _   _   \ \  /\  / /_ _| |_ ___| |__   ___ _ __ "
  Write-Host "| |  | | | '__/ _ \/ __| __/ _ \| '__| | | |   \ \/  \/ / _` | __/ __| '_ \ / _ \ '__|"
  Write-Host "| |__| | | | |  __/ (__| || (_) | |  | |_| |    \  /\  / (_| | || (__| | | |  __/ |   "
  Write-Host "|_____/|_|_|  \___|\___|\__\___/|_|   \__, |     \/  \/ \__,_|\__\___|_| |_|\___|_|   "
  Write-Host "                                       __/ |                                          "
  Write-Host "                                      |___/                                           "
  Write-Host ""

  # since the FileSystemWatcher is no longer blocking PowerShell
  # we need a way to pause PowerShell while being responsive to
  # incoming events. Use an endless loop to keep PowerShell busy:
  $symbols = @("( *    )", "(  *   )", "(   *  )", "(    * )", "(     *)", "(    * )", "(   *  )", "(  *   )",
    "( *    )", "(*     )")
  $i = 0;
  do {
    # Write symbol
    $symbol = $symbols[$i]
    Write-Host -NoNewLine "`r$symbol Watching for incoming *.dat files to $MonitoringPath" -ForegroundColor DarkCyan
    # Wait-Event waits for a second and stays responsive to events
    Wait-Event -Timeout 1
    # Increment to next symbol
    $i++
    if ($i -eq $symbols.Count) {
      $i = 0;
    }   
  } while ($true)
}
finally {
  # this gets executed when user presses CTRL+C:

  # stop monitoring
  $watcher.EnableRaisingEvents = $false
  
  # remove the event handlers
  $handlers | ForEach-Object {
    Unregister-Event -SourceIdentifier $_.Name
  }
  
  # event handlers are technically implemented as a special kind
  # of background job, so remove the jobs now:
  $handlers | Remove-Job
  
  # properly dispose the FileSystemWatcher:
  $watcher.Dispose()
  
  Write-Host ""
  Write-Warning "Event Handler disabled, monitoring ends."

  # clear DestinationPath variable
  Clear-Variable DestinationPath -scope global
}
