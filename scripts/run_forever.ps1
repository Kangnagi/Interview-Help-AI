# 프로그램 하나를 계속 살려 둔다 — 종료(오류·크래시)되면 5초 뒤 다시 실행한다.
# start_all.ps1이 서비스마다 이 스크립트를 창 없이 하나씩 띄운다. 로그는 저장소 루트의 logs/ 에 남는다.
# 루프 안의 어떤 오류(로그 파일 잠김·이동 실패 등)도 루프를 끝내지 않는다 — 10/16 재부팅 직후 터널 감시 루프가
# 재시작 기록 없이 사라져 사이트가 1033으로 꺼졌다. 그래도 루프가 끝나면 그 이유를 감시 로그에 남긴다.
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

function Write-WatchLog([string]$msg) {
    # 기록 실패로 루프가 멈추면 안 되므로 잠깐 다시 시도하고, 끝내 안 되면 버린다
    for ($i = 0; $i -lt 3; $i++) {
        try { "$(Get-Date -Format s) [$Name] $msg" | Add-Content $watchLog -Encoding UTF8 -ErrorAction Stop; return }
        catch { Start-Sleep -Milliseconds 300 }
    }
}

Write-WatchLog "감시 루프 시작 (pid $PID)"
try {
    while ($true) {
        try {
            $out = Join-Path $logDir "$Name.out.log"
            $err = Join-Path $logDir "$Name.err.log"
            foreach ($f in @($out, $err)) {   # 직전 실행 로그 1개만 보관
                if (Test-Path $f) { try { Move-Item $f "$f.prev" -Force -ErrorAction Stop } catch { } }
            }

            Write-WatchLog "시작: $FilePath $Arguments (cwd $WorkingDirectory)"
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
                $p = Start-Process @startArgs -ErrorAction Stop
                $null = $p.Handle   # 종료 코드를 읽으려면 핸들을 먼저 잡아 둬야 한다 (PowerShell 5.1)
                $p.WaitForExit()
                $code = $p.ExitCode
            } catch {
                $code = "시작 실패: $($_.Exception.Message)"
            }
            Write-WatchLog "종료 ($code) — 5초 뒤 재시작"
        } catch {
            Write-WatchLog "감시 루프 오류: $($_.Exception.Message) — 5초 뒤 재시도"
        }
        Start-Sleep -Seconds 5
    }
} finally {
    # 여기까지 오는 건 감시 루프 자체가 강제 종료될 때뿐 — 5분마다 도는 작업 스케줄러 점검이 다시 띄운다
    Write-WatchLog "감시 루프 종료 (pid $PID)"
}
