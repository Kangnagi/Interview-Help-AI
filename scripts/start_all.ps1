# 백엔드(FastAPI) · 프런트엔드(Vite) · Cloudflare 터널을 각각 감시 루프(run_forever.ps1)로 창 없이 띄운다.
# 이미 감시 중인 서비스는 건너뛰므로 여러 번 실행해도 안전하다. 로그온 시 작업 스케줄러가 자동 실행한다.
$root = Split-Path -Parent $PSScriptRoot
$runner = Join-Path $PSScriptRoot "run_forever.ps1"
# node·cloudflared는 저장소의 .tools/ 에 둔다 (gitignore). AppData에 설치한 사본은 로그온 시 작업 스케줄러에서
# 보이지 않는 경우가 있어 저장소 안 경로로 고정했다.
$node = "$root\.tools\node"
$cloudflared = "$root\.tools\cloudflared\cloudflared.exe"

$services = @(
    @{ Name = "backend";  FilePath = "$root\backend\.venv\Scripts\python.exe"; Arguments = "main.py";
       WorkingDirectory = "$root\backend" },
    @{ Name = "frontend"; FilePath = "$node\npm.cmd"; Arguments = "run dev";
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
    Start-Process powershell.exe -ArgumentList $argLine -WindowStyle Hidden
    Write-Output "[$($s.Name)] 감시 시작"
}
