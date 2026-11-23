$ErrorActionPreference = 'Stop'
$helper = Join-Path $PSScriptRoot '..\scripts\admin\Initialize-LabOidc.ps1'
$global:OidcTestPolicy = @{ use_default = $true; use_immutable_subject = $true }
$global:OidcTestMetadata = @{ full_name = 'mikkokallio/aml-mlops-arc-lab'; name = 'aml-mlops-arc-lab'; id = 222; owner = @{ login = 'mikkokallio'; id = 111 } }
$global:OidcTestScope = '/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-amlarclab-id/providers/Microsoft.ManagedIdentity/userAssignedIdentities/test-p-ci'
$global:OidcTestCredentials = @(
    foreach ($environment in @('train', 'prod', 'unrelated')) {
        @{ name = "aml-lab-github-$environment"; properties = @{
            issuer = 'https://token.actions.githubusercontent.com'
            subject = "repo:mikkokallio/aml-mlops-arc-lab:environment:$environment"
            audiences = @('api://AzureADTokenExchange')
        } }
    }
)
$global:OidcTestBodies = @{}
$global:OidcTestLogs = [System.Collections.Generic.List[object]]::new()
$global:OidcTestWrites = 0

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function gh {
    $global:LASTEXITCODE = 0
    if ($args[-1] -like '*/actions/oidc/customization/sub') {
        $global:OidcTestPolicy | ConvertTo-Json -Depth 10
    } elseif ($args[-1] -ceq 'repos/mikkokallio/aml-mlops-arc-lab') {
        $global:OidcTestMetadata | ConvertTo-Json -Depth 10
    } else { throw 'Unexpected GitHub request.' }
}
function Get-Content {
    param([string]$LiteralPath, [switch]$Raw)
    if ($LiteralPath -notlike '*rg-amlarclab-id.deployment.json') { throw 'Unexpected file read.' }
    @{ properties = @{ outputs = @{ identities = @{ value = @(@{ name = 'p-ci'; id = $global:OidcTestScope }) } } } } |
        ConvertTo-Json -Depth 10
}
function Set-Content {
    param([string]$LiteralPath, [string]$Encoding, [Parameter(ValueFromPipeline)]$Value)
    process {
        Assert-True ($LiteralPath -like '*oidc-fic-*.json') 'Unexpected file write.'
        $global:OidcTestBodies[$LiteralPath] = $Value | ConvertFrom-Json
    }
}
function Add-Content {
    param([string]$LiteralPath, [Parameter(ValueFromPipeline)]$Value)
    process {
        Assert-True ($LiteralPath -like '*admin-actions.jsonl') 'Unexpected log target.'
        $global:OidcTestLogs.Add(($Value | ConvertFrom-Json))
    }
}
function az {
    Assert-True ($args[0] -ceq 'rest') 'Unexpected Azure command.'
    $global:LASTEXITCODE = 0
    $method = $args[([array]::IndexOf($args, '--method') + 1)]
    if ($method -ceq 'get') {
        @{ value = $global:OidcTestCredentials } | ConvertTo-Json -Depth 10
    } elseif ($method -ceq 'put') {
        $url = $args[([array]::IndexOf($args, '--url') + 1)]
        $bodyPath = $args[([array]::IndexOf($args, '--body') + 1)].Substring(1)
        $name = ($url -split '\?')[0].Split('/')[-1]
        $credential = @($global:OidcTestCredentials | Where-Object name -CEQ $name)
        Assert-True ($credential.Count -eq 1) 'Replacement must target exactly one existing credential.'
        $credential[0].properties = $global:OidcTestBodies[$bodyPath].properties
        $global:OidcTestWrites++
    } else { throw 'Unexpected Azure method.' }
}

$unrelatedBefore = $global:OidcTestCredentials[2] | ConvertTo-Json -Depth 10 -Compress
& $helper -ReplaceLegacySubjects | Out-Null
Assert-True ($global:OidcTestWrites -eq 2) 'Expected exactly two replacements.'
Assert-True ($global:OidcTestCredentials.Count -eq 3) 'Credential count changed.'
Assert-True (($global:OidcTestCredentials[2] | ConvertTo-Json -Depth 10 -Compress) -ceq $unrelatedBefore) 'Unrelated credential changed.'
foreach ($environment in @('train', 'prod')) {
    $credential = $global:OidcTestCredentials | Where-Object name -CEQ "aml-lab-github-$environment"
    Assert-True ($credential.properties.subject -ceq "repo:mikkokallio@111/aml-mlops-arc-lab@222:environment:$environment") 'Immutable subject mismatch.'
}
Assert-True ($global:OidcTestLogs.Count -eq 4) 'Both attempts and results must be privately logged.'
foreach ($log in $global:OidcTestLogs) {
    Assert-True ($log.permission -ceq 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/write') 'Wrong action logged.'
    Assert-True ($log.scope -ceq $global:OidcTestScope) 'Wrong identity scope logged.'
    Assert-True ($log.oldSubject -like 'repo:mikkokallio/aml-mlops-arc-lab:environment:*') 'Old subject missing.'
    Assert-True ($log.newSubject -like 'repo:mikkokallio@111/aml-mlops-arc-lab@222:environment:*') 'New subject missing.'
}
& $helper -ReplaceLegacySubjects | Out-Null
Assert-True ($global:OidcTestWrites -eq 2 -and $global:OidcTestLogs.Count -eq 4) 'Second execution was not idempotent.'

$global:OidcTestPolicy = @{ use_default = $true; use_immutable_subject = $false }
foreach ($credential in $global:OidcTestCredentials) {
    $environment = $credential.name -replace '^aml-lab-github-', ''
    $credential.properties.subject = "repo:mikkokallio/aml-mlops-arc-lab:environment:$environment"
}
& $helper | Out-Null
Assert-True ($global:OidcTestWrites -eq 2) 'Explicit legacy policy must preserve matching legacy credentials.'
foreach ($unsupported in @(
    @{ use_default = $true },
    @{ use_default = $true; use_immutable_subject = 'true' },
    @{ use_default = $false; use_immutable_subject = $true }
)) {
    $global:OidcTestPolicy = $unsupported
    $failed = $false
    try { & $helper | Out-Null } catch { $failed = $true }
    Assert-True $failed 'Unsupported policy did not fail closed.'
}
Assert-True ($global:OidcTestWrites -eq 2) 'Unsupported policy changed federation.'
Write-Output 'PASS: immutable replacement, exact boundaries/private logs, unrelated preservation, idempotency, explicit legacy policy and unknown-policy rejection.'
