[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ResourceGroup,
    [Parameter(Mandatory)][string]$Template,
    [string]$DeploymentName = 'lab-bootstrap',
    [string[]]$TemplateParameters = @()
)

$ErrorActionPreference = 'Stop'
$directory = Join-Path $PSScriptRoot '..\.local'
$evidencePrefix = if ($DeploymentName -eq 'lab-bootstrap') { $ResourceGroup } else { "$ResourceGroup.$DeploymentName" }
New-Item -ItemType Directory -Force -Path $directory | Out-Null
$arguments = @('--resource-group', $ResourceGroup, '--template-file', $Template)
if ($TemplateParameters.Count -gt 0) {
    $arguments += @('--parameters') + $TemplateParameters
}
$preview = & az deployment group what-if @arguments --no-pretty-print --output json
if ($LASTEXITCODE -ne 0) { throw "What-if failed for $ResourceGroup." }
$preview | Set-Content -LiteralPath (Join-Path $directory "$evidencePrefix.what-if.json")
$result = & az deployment group create @arguments --name $DeploymentName --output json
$exitCode = $LASTEXITCODE
[ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    persona = 'bootstrap Owner'
    command = 'az deployment group create ' + ($arguments -join ' ') + " --name $DeploymentName --output json"
    permission = 'Microsoft.Resources/deployments/write and template resource write operations (Contributor)'
    scope = $ResourceGroup
    exitCode = $exitCode
} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
if ($exitCode -ne 0) { throw "Deployment failed for $ResourceGroup." }
$result | Set-Content -LiteralPath (Join-Path $directory "$evidencePrefix.deployment.json")
$deployment = ($result -join "`n") | ConvertFrom-Json
if ($deployment.properties.provisioningState -ne 'Succeeded') {
    throw "Deployment is not successful: $($deployment.properties.provisioningState)"
}
$deployment.properties.outputs | ConvertTo-Json -Depth 10
