# 프로그램 하나를 계속 살려 둔다 — 종료(오류·크래시)되면 5초 뒤 다시 실행한다.
# start_all.ps1이 서비스마다 이 스크립트를 창 없이 하나씩 띄운다. 로그는 저장소 루트의 logs/ 에 남는다.
param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string]$Arguments = "",
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [string]$ExtraPath = ""
)

$logDir = Join-Path (Split-Path -Parent $PSScriptRoot) "logs"
New-Item -ItemType Directory -Force $logDir | Out-Null
$watchLog = Join-Path $logDir "$Name.watchdog.log"   # 서비스별로 따로 — 여러 감시 루프가 한 파일에 쓰면 잠금 충돌이 난다
if ($ExtraPath) { $env:Path = "$ExtraPath;$env:Path" }
$env:PYTHONIOENCODING = "utf-8"

while ($true) {
    $out = Join-Path $logDir "$Name.out.log"
    $err = Join-Path $logDir "$Name.err.log"
    foreach ($f in @($out, $err)) { if (Test-Path $f) { Move-Item $f "$f.prev" -Force } }   # 직전 실행 로그 1개만 보관

    "$(Get-Date -Format s) [$Name] 시작: $FilePath $Arguments (cwd $WorkingDirectory)" | Add-Content $watchLog -Encoding UTF8
    $startArgs = @{
        FilePath               = $FilePath
        WorkingDirectory       = $WorkingDirectory
        RedirectStandardOutput = $out
        RedirectStandardError  = $err
        NoNewWindow            = $true
        PassThru               = $true
    }
    if ($Arguments) { $startArgs.ArgumentList = $Arguments }
    try {
        $p = Start-Process @startArgs
        $null = $p.Handle   # 종료 코드를 읽으려면 핸들을 먼저 잡아 둬야 한다 (PowerShell 5.1)
        $p.WaitForExit()
        $code = $p.ExitCode
    } catch {
        $code = "시작 실패: $($_.Exception.Message)"
    }
    "$(Get-Date -Format s) [$Name] 종료 ($code) — 5초 뒤 재시작" | Add-Content $watchLog -Encoding UTF8
    Start-Sleep -Seconds 5
}
