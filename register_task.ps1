# 注册本机定时重筛：每 6 小时用国内网络测活一遍，覆盖 output\clash.yaml
# 撤销： Unregister-ScheduledTask -TaskName clash-node-harvest-local -Confirm:$false
$name = "clash-node-harvest-local"
$cmd = Join-Path $PSScriptRoot "run_local.cmd"
# 计划任务直接 Execute 一个 .bat/.cmd 会以退出码 1 失败，必须包一层 cmd.exe
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$cmd`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(45) `
    -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -Hidden -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Get-ScheduledTask -TaskName $name | Format-List TaskName, State
"日志: $PSScriptRoot\output\cron.log"
