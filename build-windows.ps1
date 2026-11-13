$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$buildPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $buildPython)) { throw 'Create .venv and install requirements first; see README.md' }
& $buildPython tools/make_icon.py
if ($LASTEXITCODE) { throw 'Icon generation failed' }
& $buildPython -m PyInstaller --noconfirm --distpath dist --workpath build/windows packaging/active-control.spec
if ($LASTEXITCODE) { throw 'EXE build failed' }
$reportPath=Join-Path $PSScriptRoot 'build\windows\smoke-test.json'
$testProcess=Start-Process -FilePath (Join-Path $PSScriptRoot 'dist\ACTIVE-Control.exe') -ArgumentList '--self-test',('"{0}"' -f $reportPath) -Wait -PassThru
if ($testProcess.ExitCode) { throw 'EXE smoke test failed' }
Get-Content -LiteralPath 'build\windows\smoke-test.json'
Get-Item -LiteralPath 'dist\ACTIVE-Control.exe' | Select-Object Name,Length
