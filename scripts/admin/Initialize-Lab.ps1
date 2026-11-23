[CmdletBinding()]
param(
    [string]$Prefix = 'amlarclab',
    [string]$Location = 'swedencentral'
)

$ErrorActionPreference = 'Stop'
$logDirectory = Join-Path $PSScriptRoot '..\..\.local'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$logPath = Join-Path $logDirectory 'admin-actions.jsonl'

function Invoke-LoggedAzure {
    param([string[]]$Arguments, [string]$Permission, [string]$Scope)
    $result = & az @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        persona = 'Owner'
        command = 'az ' + ($Arguments -join ' ')
        permission = $Permission
        scope = $Scope
        exitCode = $exitCode
        result = ($result -join "`n")
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath
    if ($exitCode -ne 0) {
        throw "Azure action failed ($exitCode). See $logPath. $($result -join "`n")"
    }
    $result
}

$subscription = (& az account show --query id --output tsv)
if ($LASTEXITCODE -ne 0) { throw 'Cannot read active subscription.' }
foreach ($provider in @(
    'Microsoft.Kubernetes',
    'Microsoft.KubernetesConfiguration',
    'Microsoft.ExtendedLocation',
    'Microsoft.MachineLearningServices',
    'Microsoft.Relay'
)) {
    $state = & az provider show --namespace $provider --query registrationState --output tsv
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect provider $provider." }
    if ($state -ne 'Registered') {
        Invoke-LoggedAzure -Arguments @(
            'provider', 'register', '--namespace', $provider, '--output', 'none'
        ) -Permission "$provider/register/action" -Scope "/subscriptions/$subscription"
    }
    Write-Output "$provider`: $state"
}

foreach ($suffix in @('ml', 'edge', 'fabric', 'id')) {
    $name = "rg-$Prefix-$suffix"
    $exists = & az group exists --name $name --output tsv
    if ($LASTEXITCODE -ne 0) { throw "Cannot check resource group $name." }
    if ($exists -eq 'true') {
        throw "Resource group $name already exists. Inspect ownership before reuse."
    }
    Invoke-LoggedAzure -Arguments @(
        'group', 'create', '--name', $name, '--location', $Location,
        '--tags', 'purpose=aml-arc-lab', 'environment=lab', 'expires=2026-11-23',
        '--output', 'none'
    ) -Permission 'Microsoft.Resources/subscriptions/resourceGroups/write' `
      -Scope "/subscriptions/$subscription/resourceGroups/$name"
    Write-Output "Created $name"
}
