# Run from Nyx folder. Registers a Windows 11 idle-triggered task under the current account.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'target\release\nyx.exe'
if (-not (Test-Path $exe)) {
    throw "Compile Nyx Core first: cargo build --release (missing $exe)"
}
if (-not (Test-Path (Join-Path $root 'config\.env'))) {
    throw 'Create config\.env from config\.env.example and fill in your credentials first.'
}
$service = New-Object -ComObject Schedule.Service
$service.Connect()
$folder = $service.GetFolder('\')
$task = $service.NewTask(0)
$task.RegistrationInfo.Description = 'Nyx: run lightweight jobs only when Windows is idle and connected to AC power.'
$task.Principal.LogonType = 3 # InteractiveToken, current account; no password needed
$task.Principal.RunLevel = 0  # Least privilege
$trigger = $task.Triggers.Create(6) # TASK_TRIGGER_IDLE
$trigger.Enabled = $true
$trigger.StartBoundary = (Get-Date).AddMinutes(-1).ToString('s')
$action = $task.Actions.Create(0) # TASK_ACTION_EXEC
$action.Path = $exe
$action.Arguments = 'run'
$action.WorkingDirectory = $root
$task.Settings.Enabled = $true
$task.Settings.RunOnlyIfIdle = $true
$task.Settings.IdleSettings.StopOnIdleEnd = $true
$task.Settings.IdleSettings.RestartOnIdle = $true
$task.Settings.DisallowStartIfOnBatteries = $true
$task.Settings.StopIfGoingOnBatteries = $true
$task.Settings.WakeToRun = $false
$task.Settings.ExecutionTimeLimit = 'PT15M'
$task.Settings.MultipleInstances = 2 # Ignore new, prevents overlapping runs
$task.Settings.AllowDemandStart = $true
$task.Settings.StartWhenAvailable = $false
$task.Settings.Hidden = $false
$account = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$null = $folder.RegisterTaskDefinition('Nyx', $task, 6, $account, $null, 3)
Write-Host 'Registered task Nyx. Inspect its Conditions and History in Task Scheduler.'
Write-Host 'Windows idle is determined by Task Scheduler; idle duration settings vary by Windows version.'
