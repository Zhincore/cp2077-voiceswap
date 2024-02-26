<#
    .SYNOPSIS
        Installs required libraries and sets up VoiceSwap
    .EXAMPLE
        .\install.ps1
#>
[CmdletBinding()]
param (
    [Parameter(HelpMessage = "Skips Lib Install")]
    [switch]
    $SkipLibs
)

$libs = @{
    "OpusToolZ"     = "https://github.com/Zhincore/OpusToolZ/releases/download/v3.1/OpusToolZ.zip"
    "WolvenKit"     = "https://github.com/WolvenKit/WolvenKit/releases/download/8.12.2/WolvenKit.Console-8.12.2.zip"
    "vgmstream"     = "https://github.com/vgmstream/vgmstream-releases/releases/download/nightly/vgmstream-win64.zip"
    "wwiser"        = "https://github.com/bnnm/wwiser/archive/refs/heads/master.zip"
}

function Get-Lib {
    param (
        [parameter(Mandatory = $true)][string]$URL,
        [parameter(Mandatory = $false)][string]$Name
    )

    $FileName = ([uri]$URL).Segments[-1]
    $FolderName = (Split-Path -Path $FileName -LeafBase)

    if ($PSBoundParameters.ContainsKey("Name")) {
        $FolderName = $Name
    }

    if ($FileName -match '\.zip$') {
        $TargetPath = (Join-Path -Path ".\libs" -ChildPath $FolderName)
        $TmpPath = (Join-Path -Path ".\libs" -ChildPath $FileName)

        if (Test-Path -Path $TargetPath -PathType Container) {
            Write-Information -MessageData "Cleaning up $TargetPath and reinstalling" -InformationAction Continue

            Remove-Item -Path $TargetPath -Recurse
        }

        Write-Information -MessageData "Installing $FileName to $TargetPath" -InformationAction Continue

        Invoke-WebRequest -Uri $URL -OutFile $TmpPath 
        Expand-Archive -Path $TmpPath -DestinationPath $TargetPath
        Remove-Item -Path $TmpPath
    } else {
        $TargetPath = (Join-Path -Path ".\libs" -ChildPath $FileName)

        Write-Information -MessageData "Installing $FileName to $TargetPath" -InformationAction Continue

        Invoke-WebRequest -Uri $URL -OutFile $TargetPath
    }
}

if ($SkipLibs) {
    Write-Information -MessageData "Skip Libs" -InformationAction Continue
}
else {
    Write-Information -MessageData "Download and extract Libs" -InformationAction Continue
    
    foreach ($hash in $libs.GetEnumerator()) {
        Get-Lib -URL $hash.Value -Name $hash.Name
    }
}


Write-Information -MessageData "Create python virtual environment and activate" -InformationAction Continue

python -m venv .venv

.\.venv\Scripts\Activate

Write-Information -MessageData "Install python dependencies" -InformationAction Continue

pip install .

Write-Information -MessageData "Done" -InformationAction Continue

