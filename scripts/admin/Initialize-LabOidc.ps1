[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$directory = Join-Path $PSScriptRoot '..\..\.local'
$deployment = Get-Content (Join-Path $directory 'rg-amlarclab-id.deployment.json') -Raw | ConvertFrom-Json
$identities = @($deployment.properties.outputs.identities.value | Where-Object name -EQ 'p-ci')
if ($identities.Count -ne 1) { throw 'Expected exactly one existing P-CI identity in the private deployment outputs.' }
$identity = $identities[0]
$scope = $identity.id
if ($scope -notmatch '^/subscriptions/[^/]+/resourceGroups/rg-amlarclab-id/providers/Microsoft.ManagedIdentity/userAssignedIdentities/[^/]+$') {
    throw 'P-CI identity is outside the approved dedicated identity resource group.'
}
$baseUrl = "https://management.azure.com$scope/federatedIdentityCredentials"
$apiVersion = '2023-01-31'
$list = & az rest --method get --url "${baseUrl}?api-version=$apiVersion" --output json --only-show-errors 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect existing P-CI federated credentials; no changes made.' }
$existing = @((($list -join "`n") | ConvertFrom-Json).value)

foreach ($environment in @('train', 'prod')) {
    $name = "aml-lab-github-$environment"
    $subject = "repo:mikkokallio/aml-mlops-arc-lab:environment:$environment"
    $issuer = 'https://token.actions.githubusercontent.com'
    $audience = 'api://AzureADTokenExchange'
    $matching = @($existing | Where-Object {
        $_.properties.issuer -eq $issuer -and $_.properties.subject -eq $subject -and
        @($_.properties.audiences).Count -eq 1 -and $_.properties.audiences[0] -eq $audience
    })
    if ($matching.Count -gt 0) {
        Write-Output "$environment federation already matches; preserved."
        continue
    }
    if (@($existing | Where-Object { $_.name -eq $name -or ($_.properties.issuer -eq $issuer -and $_.properties.subject -eq $subject) }).Count -gt 0) {
        throw "Conflicting $environment federation exists; preserved without replacement."
    }
    $credentialScope = "$scope/federatedIdentityCredentials/$name"
    $bodyPath = Join-Path $directory "oidc-fic-$environment.json"
    @{ properties = @{ issuer = $issuer; subject = $subject; audiences = @($audience) } } |
        ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $bodyPath -Encoding utf8
    $arguments = @(
        'rest', '--method', 'put',
        '--url', "https://management.azure.com${credentialScope}?api-version=$apiVersion",
        '--body', "@$bodyPath", '--output', 'none', '--only-show-errors'
    )
    $reason = "Enable short-lived GitHub OIDC for the approved lab $environment environment; authentication/approval probe only."
    [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        persona = 'Owner'
        command = 'az ' + ($arguments -join ' ')
        permission = 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/write'
        scope = $scope
        credentialScope = $credentialScope
        reason = $reason
        repeatRole = 'Owner or a custom role with the logged action on this exact P-CI identity'
        result = 'ATTEMPT'
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
    $result = & az @arguments 2>&1
    $exitCode = $LASTEXITCODE
    [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        persona = 'Owner'
        command = 'az ' + ($arguments -join ' ')
        permission = 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/write'
        scope = $scope
        credentialScope = $credentialScope
        reason = $reason
        repeatRole = 'Owner or a custom role with the logged action on this exact P-CI identity'
        exitCode = $exitCode
        result = if ($exitCode -eq 0) { 'PASS' } else { $result -join "`n" }
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
    if ($exitCode -ne 0) { throw "$environment federation creation failed; details are in the private admin action log." }
    Write-Output "$environment federation created."
}

$verified = & az rest --method get --url "${baseUrl}?api-version=$apiVersion" --output json --only-show-errors 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Unable to verify P-CI federation after provisioning.' }
$credentials = @((($verified -join "`n") | ConvertFrom-Json).value)
foreach ($environment in @('train', 'prod')) {
    $match = @($credentials | Where-Object {
        $_.properties.issuer -eq 'https://token.actions.githubusercontent.com' -and
        $_.properties.subject -eq "repo:mikkokallio/aml-mlops-arc-lab:environment:$environment" -and
        @($_.properties.audiences).Count -eq 1 -and
        $_.properties.audiences[0] -eq 'api://AzureADTokenExchange'
    })
    if ($match.Count -ne 1) { throw "$environment federation verification failed." }
}
Write-Output 'PASS: both environment federations verified; unrelated credentials preserved.'
