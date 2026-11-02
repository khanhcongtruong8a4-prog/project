param([string]$PythonExe)
$ErrorActionPreference = 'Stop'
if (-not $PythonExe) {
    $candidates = @(
        (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
        (Join-Path $PSScriptRoot '..\..\work\python\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            $PythonExe = (Resolve-Path -LiteralPath $candidate).Path
            break
        }
    }
}
if (-not $PythonExe) {
    throw 'Pass -PythonExe with a Python 3.13 interpreter containing requirements.txt. See README.md.'
}
& $PythonExe (Join-Path $PSScriptRoot 'review_checks.py')
exit $LASTEXITCODE
