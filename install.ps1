mkdir libs
Set-Location libs

# Download WolvenKit
Invoke-WebRequest https://github.com/WolvenKit/WolvenKit/releases/download/8.10.0/WolvenKit.Console-1.10.0.zip -o WolvenKit.zip
mkdir WolvenKit
Set-Location WolvenKit
tar -xf ..\WolvenKit.zip
Set-Location ..
Remove-Item WolvenKit.zip

# Download ww2ogg
Invoke-WebRequest https://github.com/hcs64/ww2ogg/releases/download/0.24/ww2ogg024.zip -o ww2ogg.zip
mkdir ww2ogg
Set-Location ww2ogg
tar -xf ..\ww2ogg.zip
Set-Location ..
Remove-Item ww2ogg.zip

# Return to previous folder
Set-Location ..

# Create a virtual environment and activate it
py -m venv .venv
.\.venv\Scripts\activate

# Install the project
pip install .

Write-Host "Done!"
