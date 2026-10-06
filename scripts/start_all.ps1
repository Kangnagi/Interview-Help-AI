# 백엔드(FastAPI) · 프런트엔드(Vite) · Cloudflare 터널을 각각 감시 루프(run_forever.ps1)로 창 없이 띄운다.
# 이미 감시 중인 서비스는 건너뛰므로 여러 번 실행해도 안전하다. 로그온 시 작업 스케줄러가 자동 실행한다.
# 프런트엔드는 기본이 운영 방식(npm run serve: 빌드 후 vite preview — 첫 화면이 빠름)이다.
# -Dev를 주면 개발 서버(npm run dev: 화면 코드 수정이 바로 반영되지만 첫 로딩이 느림)로 띄운다.
# 이미 떠 있는 프런트엔드의 방식을 바꾸거나 다시 빌드하려면 restart_frontend.ps1을 쓴다.
param([switch]$Dev)
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_forever.ps1"
# node·cloudflared는 저장소의 .tools/ 에 둔다 (gitignore). AppData에 설치한 사본은 로그온 시 작업 스케줄러에서
# 보이지 않는 경우가 있어 저장소 안 경로로 고정했다.
$node = "$root\.tools\node"
$cloudflared = "$root\.tools\cloudflared\cloudflared.exe"

$services = @(
    @{ Name = "backend";  FilePath = "$root\backend\.venv\Scripts\python.exe"; Arguments = "main.py";
       WorkingDirectory = "$root\backend" },
    @{ Name = "frontend"; FilePath = "$node\npm.cmd"; Arguments = $(if ($Dev) { "run dev" } else { "run serve" });
       WorkingDirectory = "$root\frontend"; ExtraPath = $node },
    @{ Name = "tunnel";   FilePath = $cloudflared;
       Arguments = "tunnel --config $env:USERPROFILE\.cloudflared\config.yml run"; WorkingDirectory = $env:USERPROFILE }
)

$watchers = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -like "*run_forever.ps1*" }

foreach ($s in $services) {
    if ($watchers | Where-Object { $_.CommandLine -like "*-Name $($s.Name) *" }) {
        Write-Output "[$($s.Name)] 이미 감시 중 — 건너뜀"
        continue
    }
    $argLine = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$runner`" -Name $($s.Name) " +
               "-FilePath `"$($s.FilePath)`" -Arguments `"$($s.Arguments)`" -WorkingDirectory `"$($s.WorkingDirectory)`""
    if ($s.ExtraPath) { $argLine += " -ExtraPath `"$($s.ExtraPath)`"" }
    # WMI(Win32_Process.Create)로 띄워 이 스크립트를 실행한 창 · 세션과 끊는다.
    # Start-Process로 띄우면 실행한 쪽의 하위 프로세스가 되어, 그 창이나 세션이 닫힐 때 감시 루프와 서비스가 같이 꺼졌다
    # (10/6 프런트엔드만 꺼져 사이트 502).
    $startup = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ ShowWindow = [uint16]0 }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = "powershell.exe $argLine"; CurrentDirectory = $root; ProcessStartupInformation = $startup }
    if ($r.ReturnValue -eq 0) {
        Write-Output "[$($s.Name)] 감시 시작 (pid $($r.ProcessId))"
    } else {
        Start-Process powershell.exe -ArgumentList $argLine -WindowStyle Hidden
        Write-Output "[$($s.Name)] 감시 시작 — WMI 실행 실패(코드 $($r.ReturnValue))로 일반 방식 사용, 이 창을 닫으면 같이 꺼질 수 있음"
    }
}
