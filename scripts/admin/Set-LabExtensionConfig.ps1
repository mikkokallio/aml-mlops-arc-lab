[CmdletBinding()]
param(
    [string[]]$Settings = @(),
    [Parameter(Mandatory)][string]$Reason,
    [string]$Version,
    [switch]$RestoreAutomaticMinorUpgrades
)

$ErrorActionPreference = 'Stop'
if ($Version -and $RestoreAutomaticMinorUpgrades) {
    throw 'A pinned version cannot be combined with automatic-minor restoration.'
}
if (-not $Settings.Count -and -not $Version -and -not $RestoreAutomaticMinorUpgrades) {
    throw 'Specify configuration settings, a version, or automatic-minor restoration.'
}
$directory = Join-Path $PSScriptRoot '..\..\.local'
$env:AZURE_EXTENSION_DIR = Join-Path $directory 'az-extensions'
$arguments = @(
    'k8s-extension', 'update', '--name', 'azureml',
    '--cluster-type', 'connectedClusters',
    '--cluster-name', 'arc-amlarclab',
    '--resource-group', 'rg-amlarclab-edge',
    '--yes', '--output', 'json'
)
if ($Settings.Count) {
    $arguments += @('--configuration-settings') + $Settings
}
if ($Version) {
    $arguments += @('--auto-upgrade-mode', 'none', '--version', $Version)
}
if ($RestoreAutomaticMinorUpgrades) {
    $arguments += @('--auto-upgrade-mode', 'compatible')
}
$result = & az @arguments 2>&1
$exitCode = $LASTEXITCODE
$result | Set-Content -LiteralPath (Join-Path $directory 'aml-extension-update.log')
[ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    persona = 'Owner'
    command = 'az ' + ($arguments -join ' ')
    permission = 'Microsoft.KubernetesConfiguration/extensions/write'
    scope = 'Dedicated Arc cluster azureml extension'
    reason = $Reason
    exitCode = $exitCode
} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
$result | Write-Output
if ($exitCode -ne 0) { throw 'AML Kubernetes extension update failed.' }
