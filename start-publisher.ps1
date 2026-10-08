$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
$bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
if (Test-Path -LiteralPath $bundledPython) {
    $pythonPath = $bundledPython
} elseif ($pythonCommand) {
    $pythonPath = $pythonCommand.Source
} else {
    throw 'Python 3.11 이상을 설치한 뒤 다시 실행하세요.'
}
& $pythonPath -m counter_note build
if ($LASTEXITCODE -ne 0) { throw '페이지 생성에 실패했습니다.' }
Write-Host '브라우저에서 http://127.0.0.1:8765 를 여세요. 종료: Ctrl+C'
& $pythonPath -m counter_note serve --publisher
