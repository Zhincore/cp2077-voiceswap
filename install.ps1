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
    "CpBnkReader" = "https://github.com/Zhincore/CpBnkReader/releases/download/v1.4/CpBnkReader.zip"
    "OpusToolZ"   = "https://github.com/Zhincore/OpusToolZ/releases/download/v3.1/OpusToolZ.zip"
    "WolvenKit"   = "https://github.com/WolvenKit/WolvenKit/releases/download/8.12.1/WolvenKit.Console-8.12.1.zip"
    "ww2ogg"      = "https://github.com/hcs64/ww2ogg/releases/download/0.24/ww2ogg024.zip"
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

    $TargetPath = (Join-Path -Path ".\libs" -ChildPath $FolderName)

    if (Test-Path -Path $TargetPath -PathType Container) {
        Write-Information -MessageData "Cleaning up $TargetPath and reinstalling" -InformationAction Continue

        Remove-Item -Path $TargetPath -Recurse
    }

    Write-Information -MessageData "Installing $FileName to $TargetPath" -InformationAction Continue

    Invoke-WebRequest -Uri $URL -OutFile $FileName
    Expand-Archive -Path $FileName -DestinationPath $TargetPath
    Remove-Item -Path $FileName
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

