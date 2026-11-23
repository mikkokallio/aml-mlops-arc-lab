[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PrincipalId,
    [ValidateSet('ServicePrincipal', 'User', 'Group')][string]$PrincipalType = 'ServicePrincipal',
    [Parameter(Mandatory)][string]$Role,
    [Parameter(Mandatory)][string]$Scope,
    [Parameter(Mandatory)][string]$Reason
)

$ErrorActionPreference = 'Stop'
$directory = Join-Path $PSScriptRoot '..\..\.local'
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$arguments = @(
    'role', 'assignment', 'create',
    '--assignee-object-id', $PrincipalId,
    '--assignee-principal-type', $PrincipalType,
    '--role', $Role,
    '--scope', $Scope,
    '--output', 'json'
)
$result = & az @arguments 2>&1
$exitCode = $LASTEXITCODE
[ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    persona = 'Owner'
    command = 'az ' + ($arguments -join ' ')
    permission = 'Microsoft.Authorization/roleAssignments/write'
    scope = $Scope
    role = $Role
    reason = $Reason
    exitCode = $exitCode
    result = ($result -join "`n")
} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
if ($exitCode -ne 0) { throw "Role assignment failed: $($result -join "`n")" }
Write-Output "Assigned $Role. Reason: $Reason"
