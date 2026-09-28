<#
.SYNOPSIS
  Registra Avatar WhatsApp 24/7 como tarea programada de Windows.
.DESCRIPTION
  Crea la tarea "AvatarWhatsApp247" que arranca whatsapp_24x7.py al iniciar
  sesión (obligatorio: el navegador headed necesita escritorio interactivo) y
  la reintenta si falla. Requiere PowerShell con elevación (admin).
.PARAMETER Uninstall
  Elimina la tarea en vez de crearla.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File Install-AvatarWhatsApp247.ps1 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true)]
param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$TaskName = "AvatarWhatsApp247"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $Root "whatsapp_24x7.py"
$LogDir = Join-Path $env:TEMP "opencode"

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return ([Security.Principal.WindowsPrincipal]$id).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
}

if (-not (Test-Path -LiteralPath $Runner)) {
    throw "No existe $Runner"
}
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python no está en PATH" }

if ($Uninstall) {
    if ($PSCmdlet.ShouldProcess($TaskName, "Eliminar tarea programada")) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Tarea $TaskName eliminada."
    }
    return
}

if (-not (Test-IsAdmin)) {
    throw "Ejecuta este script en PowerShell como Administrador."
}

$action = New-ScheduledTaskAction -Execute $py `
    -Argument "`"$Runner`"" -WorkingDirectory $Root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit 0
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

if ($PSCmdlet.ShouldProcess($TaskName, "Registrar tarea programada")) {
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Force | Out-Null
    Write-Host "Tarea $TaskName registrada. Arranca al iniciar sesión."
    Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State | Format-Table
}
