# 프런트엔드만 다시 띄운다 (백엔드·터널은 그대로 — 모델을 다시 불러오지 않는다).
#   restart_frontend.ps1        : 운영 방식으로 다시 빌드해서 띄움 — 화면 코드를 고친 뒤 반영할 때
#   restart_frontend.ps1 -Dev   : 개발 서버로 전환 — 화면 코드를 계속 고치며 볼 때
# 빌드하는 동안(약 10초) 사이트 접속이 잠깐 끊긴다.
param([switch]$Dev)

Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
    Where-Object { $_.CommandLine -like "*run_forever.ps1*-Name frontend *" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -Confirm:$false -ErrorAction SilentlyContinue }

& (Join-Path $PSScriptRoot "start_all.ps1") -Dev:$Dev
