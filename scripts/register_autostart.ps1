# Windows 로그온 시 start_all.ps1이 자동 실행되도록 작업 스케줄러에 등록한다 (현재 사용자, 관리자 권한 불필요).
# 해제: Unregister-ScheduledTask -TaskName InterviewHelpAI-Server -Confirm:$false
$taskName = "InterviewHelpAI-Server"
$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSScriptRoot\start_all.ps1`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force `
    -Description "Interview-Help-AI 백엔드·프런트엔드·Cloudflare 터널 자동 실행 (scripts/start_all.ps1)" | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
