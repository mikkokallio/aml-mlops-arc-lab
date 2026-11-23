<#
.SYNOPSIS
Reads Fabric prerequisite metadata without changing resources or Azure login context.
.DESCRIPTION
Uses the operator's current login for metadata and one synchronous VM Run Command
with P-CI in an isolated CLI configuration. Raw evidence is private under .local.
An account-level OneLake HEAD only tests reachability, not workspace data permission
or the external-app tenant setting. Failed authorization never implies no capacity.
#>
[CmdletBinding()]
param([switch]$SkipVm)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$run = 'fabric-prerequisites-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$directory = Join-Path $root ".local\$run"
$null = New-Item -ItemType Directory -Path $directory -Force
$edge = (Get-Content (Join-Path $root '.local\rg-amlarclab-edge.deployment.json') -Raw | ConvertFrom-Json).properties.outputs
$identities = (Get-Content (Join-Path $root '.local\rg-amlarclab-id.deployment.json') -Raw | ConvertFrom-Json).properties.outputs.identities.value
$subscription = ($edge.vmId.value -split '/')[2]
$results = [System.Collections.Generic.List[object]]::new()

function Invoke-MetadataProbe {
    param([string]$Name, [string]$Uri, [string]$Resource)
    $tokenError = Join-Path $directory "$Name.token-error.txt"
    $token = & az account get-access-token --resource $Resource --query accessToken --output tsv 2> $tokenError
    if ($LASTEXITCODE -ne 0) {
        $results.Add([pscustomobject]@{ probe = $Name; stage = 'token'; error = (Get-Content $tokenError -Raw) })
        return
    }
    try {
        $response = Invoke-WebRequest -Method Get -Uri $Uri -Headers @{ Authorization = "Bearer $token" } -TimeoutSec 45 -SkipHttpErrorCheck
    }
    finally { $token = $null }
    $raw = @{ status = [int]$response.StatusCode; headers = $response.Headers; body = $response.Content }
    $raw | ConvertTo-Json -Depth 30 | Set-Content (Join-Path $directory "$Name.raw.json")
    $body = $response.Content | ConvertFrom-Json
    $entry = [ordered]@{ probe = $Name; status = [int]$response.StatusCode }
    if ($response.StatusCode -eq 200) {
        if ($Name -eq 'operator-provider') {
            $entry.registrationState = $body.registrationState
            $entry.capacityApiVersions = @($body.resourceTypes | Where-Object resourceType -eq 'capacities' | ForEach-Object apiVersions)
        }
        else {
            $entry.count = @($body.value).Count
            $entry.hasMore = [bool]($body.nextLink -or $body.continuationToken)
            if ($Name -eq 'operator-arm-capacities') {
                $entry.types = @($body.value | Group-Object type | Select-Object Name, Count)
                $entry.skus = @($body.value | Group-Object { $_.sku.name } | Select-Object Name, Count)
            }
            if ($Name -eq 'operator-skus') {
                $entry.f2 = @($body.value | Where-Object name -eq 'F2')
            }
        }
    }
    else {
        $entry.error = $body
    }
    $results.Add([pscustomobject]$entry)
}

$arm = "https://management.azure.com/subscriptions/$subscription/providers/Microsoft.Fabric"
Invoke-MetadataProbe 'operator-provider' "$($arm)?api-version=2021-04-01" 'https://management.azure.com/'
Invoke-MetadataProbe 'operator-arm-capacities' "$arm/capacities?api-version=2023-11-01" 'https://management.azure.com/'
Invoke-MetadataProbe 'operator-skus' "$arm/skus?api-version=2023-11-01" 'https://management.azure.com/'
Invoke-MetadataProbe 'operator-fabric-capacities' 'https://api.fabric.microsoft.com/v1/capacities' 'https://api.fabric.microsoft.com'
$results | ConvertTo-Json -Depth 30 | Set-Content (Join-Path $directory 'operator-summary.json')

if (-not $SkipVm) {
    $ci = $identities | Where-Object name -eq 'p-ci'
    if (-not $ci.clientId) { throw 'P-CI client ID missing from private deployment outputs.' }
    $variables = [ordered]@{
        LAB_SUBSCRIPTION = $subscription
        LAB_CI_CLIENT_ID = $ci.clientId
        LAB_FABRIC_RUN = $run
        LAB_FABRIC_PROBE_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'probe-prerequisites.py')))
    }
    $prefix = ($variables.GetEnumerator() | ForEach-Object { "export $($_.Key)='$($_.Value)'" }) -join "`n"
    $script = Join-Path $directory 'run-vm.sh'
    [IO.File]::WriteAllText($script, $prefix + "`n" + (Get-Content (Join-Path $PSScriptRoot 'probe-prerequisites.sh') -Raw), [Text.UTF8Encoding]::new($false))
    $remote = & (Join-Path $root 'scripts\Invoke-Edge.ps1') -Script $script -EvidenceName $run
    $remote | Set-Content (Join-Path $directory 'vm-output.txt')
    $line = ($remote -join "`n") -split "`n" | Where-Object { $_.StartsWith('FABRIC_PROBE_JSON=') } | Select-Object -First 1
    if (-not $line) { throw 'VM probe summary missing; inspect private Run Command evidence.' }
    $line.Substring('FABRIC_PROBE_JSON='.Length) | Set-Content (Join-Path $directory 'ci-summary.json')
}

Write-Output "FABRIC_EVIDENCE=$directory"
$results | ForEach-Object { Write-Output ("PROBE {0} status={1} stage={2} count={3}" -f $_.probe, $_.status, $_.stage, $_.PSObject.Properties['count'].Value) }
if (-not $SkipVm) {
    (Get-Content (Join-Path $directory 'ci-summary.json') -Raw | ConvertFrom-Json).results |
        ForEach-Object { Write-Output ("PROBE {0} status={1} stage={2} count={3} code={4}" -f $_.probe, $_.status, $_.stage, $_.PSObject.Properties['count'].Value, $_.errorCode) }
}
