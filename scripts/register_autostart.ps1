# Windows 로그온 시 start_all.ps1이 자동 실행되도록 작업 스케줄러에 등록한다 (현재 사용자, 관리자 권한 불필요).
# 로그온 뒤에도 5분마다 다시 실행해, 감시 루프가 사라진 서비스가 있으면 다시 띄운다 (살아 있는 서비스는 건너뜀).
# conhost --headless로 띄워 5분마다 콘솔 창이 깜빡이지 않게 한다.
# 해제: Unregister-ScheduledTask -TaskName InterviewHelpAI-Server -Confirm:$false
$taskName = "InterviewHelpAI-Server"
$action = New-ScheduledTaskAction -Execute "conhost.exe" `
    -Argument "--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\start_all.ps1`""
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$every5min = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($logon, $every5min) -Settings $settings -Force `
    -Description "Interview-Help-AI 백엔드·프런트엔드·Cloudflare 터널 자동 실행 + 5분마다 점검 (scripts/start_all.ps1)" | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
