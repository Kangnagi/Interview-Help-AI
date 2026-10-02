# git에 없는 것(비밀값 · DB · 모델 · 학습 데이터)을 USB 같은 다른 드라이브로 백업한다.
#   backup.ps1 -Dest E:\           : 기본 백업 (약 0.8GB) — 서비스 복구에 필요한 것 + 다시 만들 수 없는 데이터
#   backup.ps1 -Dest E:\ -Full     : 전체 백업 (약 1.3GB) — 예전 어댑터 전부 + WSL 학습 데이터까지
# 결과: <Dest>\InterviewHelpAI-backup\<날짜-시각>\  (MANIFEST.txt에 파일별 SHA256, RESTORE.txt에 복구 방법)
# 서비스를 켠 채로 실행해도 된다 — DB는 SQLite 백업 기능으로 일관된 사본을 만든다.
# 예전 백업은 지우지 않는다. USB 용량이 차면 오래된 날짜 폴더를 직접 지운다.
param(
    [Parameter(Mandatory = $true)][string]$Dest,
    [switch]$Full,
    [switch]$AllowSameDrive   # 시험용: 같은 드라이브(C:)로도 백업 허용
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"
$desktop = [Environment]::GetFolderPath("Desktop")

# ── 대상 확인 ─────────────────────────────────────────────
if (-not (Test-Path $Dest)) { throw "백업 위치가 없습니다: $Dest (USB가 꽂혀 있는지, 드라이브 문자가 맞는지 확인)" }
$destFull = (Resolve-Path $Dest).Path
if ($destFull.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) { throw "저장소 안으로는 백업할 수 없습니다: $destFull" }
if (-not $AllowSameDrive -and ([IO.Path]::GetPathRoot($destFull) -ieq [IO.Path]::GetPathRoot($root))) {
    throw "서버와 같은 드라이브($([IO.Path]::GetPathRoot($root)))에는 백업하지 않습니다 — PC가 고장 나면 같이 사라집니다. USB 드라이브를 지정하세요."
}

# ── 백업 목록: 이름, 원본, 백업 안 폴더 ───────────────────────
$items = [System.Collections.Generic.List[object]]::new()
function Add-Backup($name, $src, $sub, [switch]$Optional) { $items.Add([pscustomobject]@{ Name = $name; Src = $src; Sub = $sub; Optional = [bool]$Optional }) }

Add-Backup "비밀값 (.env)"                 "$root\backend\.env"                         "secrets"
Add-Backup "Cloudflare 터널 인증"          "$env:USERPROFILE\.cloudflared"              "secrets\cloudflared"
Add-Backup "사용자 업로드"                 "$root\backend\uploads"                      "uploads"
Add-Backup "학습 데이터 (git 제외분)"      "$root\backend\training\data"                "training_data"
Add-Backup "평가 로그"                     "$root\backend\training\*.log"               "training_logs"  -Optional
Add-Backup "진행 문서 · 사람 검토 시트"    "$desktop\내일의 면접"                        "docs"           -Optional
Add-Backup "원본 면접 데이터 (llama-finetune.zip)" "$desktop\llama-finetune.zip"         "raw"            -Optional
if ($Full) {
    Add-Backup "채점 · 피드백 어댑터 전부"  "$root\backend\ai_models"                    "ai_models"
} else {
    foreach ($a in "bllossom-score-adapter-b3", "bllossom-score-adapter-b2", "bllossom-score-adapter-b1") {
        Add-Backup "어댑터 $a" "$root\backend\ai_models\$a" "ai_models\$a"
    }
}

# ── 용량 확인 ─────────────────────────────────────────────
function Get-Size($p) {
    if (-not (Test-Path $p)) { return 0 }
    $s = (Get-ChildItem $p -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    if ($s) { [int64]$s } else { 0 }
}
$need = ($items | ForEach-Object { Get-Size $_.Src } | Measure-Object -Sum).Sum + (Get-Size "$root\backend\interview.db")
$drive = Get-PSDrive -Name ($destFull.Substring(0, 1))
if ($drive.Free -lt $need * 1.1) { throw ("USB 남은 공간 부족: 필요 {0:N0}MB, 남음 {1:N0}MB" -f ($need / 1MB), ($drive.Free / 1MB)) }

$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$commit = try { (git -C $root rev-parse --short HEAD 2>$null) } catch { "알 수 없음" }
$out = Join-Path $destFull "InterviewHelpAI-backup\$stamp"
New-Item -ItemType Directory -Force $out | Out-Null
Write-Output ("백업 시작 → {0}  (약 {1:N0}MB, {2})" -f $out, ($need / 1MB), $(if ($Full) { "전체" } else { "기본" }))

# ── 복사 ──────────────────────────────────────────────────
$skipped = @()
foreach ($it in $items) {
    if (-not (Test-Path $it.Src)) {
        if ($it.Optional) { $skipped += "$($it.Name) — 없음 ($($it.Src))"; continue }
        throw "필수 항목이 없습니다: $($it.Name) ($($it.Src))"
    }
    $target = Join-Path $out $it.Sub
    New-Item -ItemType Directory -Force $target | Out-Null
    if ((Get-Item $it.Src -Force) -is [IO.DirectoryInfo]) {
        Copy-Item -Path (Join-Path $it.Src "*") -Destination $target -Recurse -Force
    } else {
        Copy-Item -Path $it.Src -Destination $target -Force
    }
    Write-Output "  ✓ $($it.Name)"
}

# DB: 서비스가 쓰는 중이어도 깨지지 않게 SQLite 백업 기능으로 복사
$dbDir = Join-Path $out "db"
New-Item -ItemType Directory -Force $dbDir | Out-Null
$code = "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); " +
        "print(d.execute('pragma integrity_check').fetchone()[0], d.execute('select count(*) from users').fetchone()[0]); d.close(); s.close()"
$r = & $py -c $code "$root\backend\interview.db" "$dbDir\interview.db"
if ($LASTEXITCODE -ne 0) { throw "DB 백업 실패" }
$ok, $users = "$r".Split(" ")
if ($ok -ne "ok") { throw "DB 사본 무결성 검사 실패: $r" }
Write-Output "  ✓ DB (무결성 검사 정상, 사용자 $($users)명)"

# WSL 학습 데이터 (전체 백업일 때만, WSL이 없으면 건너뜀)
if ($Full) {
    $wslDir = Join-Path $out "wsl_llama_train_data"
    New-Item -ItemType Directory -Force $wslDir | Out-Null
    $wslTarget = "/mnt/" + $wslDir.Substring(0, 1).ToLower() + ($wslDir.Substring(2) -replace "\\", "/")
    wsl.exe -e bash -c "cp -r ~/llama-train/data/. '$wslTarget/'" 2>$null
    if ($LASTEXITCODE -eq 0) { Write-Output "  ✓ WSL 학습 데이터" } else { $skipped += "WSL 학습 데이터 — 복사 실패(WSL 꺼짐 또는 USB를 WSL에서 못 봄)" }
}

# ── 확인 파일 ─────────────────────────────────────────────
$files = Get-ChildItem $out -Recurse -File -Force
$manifest = $files | ForEach-Object {
    "{0}  {1,12}  {2}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Length, $_.FullName.Substring($out.Length + 1)
}
$manifest | Set-Content (Join-Path $out "MANIFEST.txt") -Encoding UTF8

@"
Interview-Help-AI 백업 $stamp ($(if ($Full) { "전체" } else { "기본" }))
원본 PC: $env:COMPUTERNAME / 저장소: $root / 커밋: $commit

복구 순서 (새 PC 또는 다시 설치한 PC)
1. GitHub에서 코드 받기 → README.md의 '개인 PC에서 실행하기' 1~3번 (가상환경, GPU용 PyTorch, 패키지)
2. secrets\.env                 → backend\.env
3. secrets\cloudflared\*        → %USERPROFILE%\.cloudflared\   (서버 PC로 쓸 때만, 터널 인증)
4. db\interview.db              → backend\interview.db   (서비스를 끈 상태에서 덮어쓰기)
5. uploads\*                    → backend\uploads\
6. ai_models\*                  → backend\ai_models\
7. training_data\*              → backend\training\data\
8. 서버 PC라면 scripts\register_autostart.ps1 → scripts\start_all.ps1

파일이 온전한지 확인: MANIFEST.txt의 SHA256과 비교 (PowerShell: Get-FileHash <파일> -Algorithm SHA256)
주의: secrets 폴더에는 비밀번호 · 키 · 터널 인증서가 있습니다. USB를 잃어버리면 바로 키를 바꾸고 터널을 다시 만드세요.
"@ | Set-Content (Join-Path $out "RESTORE.txt") -Encoding UTF8

$total = ($files | Measure-Object Length -Sum).Sum
Write-Output ("완료: 파일 {0}개, {1:N0}MB → {2}" -f $files.Count, ($total / 1MB), $out)
foreach ($s in $skipped) { Write-Output "  (건너뜀) $s" }
Write-Output "※ secrets 폴더에 비밀값이 들어 있습니다. USB는 BitLocker 등으로 암호화해 보관하세요."
