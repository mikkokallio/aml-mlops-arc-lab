[CmdletBinding()]
param([switch]$ReplaceLegacySubjects)

$ErrorActionPreference = 'Stop'
$repository = 'mikkokallio/aml-mlops-arc-lab'
$githubArguments = @('api', '-H', 'X-GitHub-Api-Version: 2026-03-10')
$policyResponse = & gh @githubArguments "repos/$repository/actions/oidc/customization/sub" 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect GitHub OIDC subject policy; no changes made.' }
$policy = ($policyResponse -join "`n") | ConvertFrom-Json
if ($policy.use_default -isnot [bool] -or -not $policy.use_default -or
    $policy.use_immutable_subject -isnot [bool] -or @($policy.include_claim_keys).Where({ $null -ne $_ }).Count -gt 0) {
    throw 'Unknown or unsupported GitHub OIDC subject policy; no changes made.'
}
$repositoryResponse = & gh @githubArguments "repos/$repository" 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Unable to inspect GitHub repository identity; no changes made.' }
$metadata = ($repositoryResponse -join "`n") | ConvertFrom-Json
if ($metadata.full_name -cne $repository -or
    "$($metadata.owner.login)/$($metadata.name)" -cne $repository -or
    "$($metadata.owner.id)" -notmatch '^[1-9][0-9]*$' -or "$($metadata.id)" -notmatch '^[1-9][0-9]*$') {
    throw 'GitHub repository identity verification failed; no changes made.'
}
$subjectPrefix = "repo:$repository"
if ($policy.use_immutable_subject) {
    $subjectPrefix = "repo:$($metadata.owner.login)@$($metadata.owner.id)/$($metadata.name)@$($metadata.id)"
}
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
    $subject = "${subjectPrefix}:environment:$environment"
    $issuer = 'https://token.actions.githubusercontent.com'
    $audience = 'api://AzureADTokenExchange'
    $matching = @($existing | Where-Object {
        $_.properties.issuer -ceq $issuer -and $_.properties.subject -ceq $subject -and
        @($_.properties.audiences).Count -eq 1 -and $_.properties.audiences[0] -ceq $audience
    })
    if ($matching.Count -gt 0) {
        Write-Output "$environment federation already matches; preserved."
        continue
    }
    $named = @($existing | Where-Object name -CEQ $name)
    $oldSubject = $null
    if ($named.Count -gt 0) {
        $legacySubject = "repo:${repository}:environment:$environment"
        if (-not $ReplaceLegacySubjects -or -not $policy.use_immutable_subject -or $named.Count -ne 1 -or
            $named[0].properties.subject -cne $legacySubject -or $named[0].properties.issuer -cne $issuer -or
            @($named[0].properties.audiences).Count -ne 1 -or $named[0].properties.audiences[0] -cne $audience) {
            throw "Conflicting $environment federation exists; preserved without replacement."
        }
        $oldSubject = $named[0].properties.subject
    } elseif ($ReplaceLegacySubjects) {
        throw "Expected existing $environment federation is missing; replacement mode cannot create credentials."
    }
    if (@($existing | Where-Object {
        $_.name -cne $name -and $_.properties.issuer -ceq $issuer -and $_.properties.subject -ceq $subject
    }).Count -gt 0) {
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
    if ($null -ne $oldSubject) {
        $reason = "Replace the exact legacy $environment subject with GitHub's verified immutable repository subject after observed AADSTS700213; retain issuer, audience and environment boundary."
    }
    [ordered]@{
        timestamp = (Get-Date).ToUniversalTime().ToString('o')
        persona = 'Owner'
        command = 'az ' + ($arguments -join ' ')
        permission = 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials/write'
        scope = $scope
        credentialScope = $credentialScope
        oldSubject = $oldSubject
        newSubject = $subject
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
        oldSubject = $oldSubject
        newSubject = $subject
        reason = $reason
        repeatRole = 'Owner or a custom role with the logged action on this exact P-CI identity'
        exitCode = $exitCode
        result = if ($exitCode -eq 0) { 'PASS' } else { $result -join "`n" }
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
    if ($exitCode -ne 0) { throw "$environment federation creation failed; details are in the private admin action log." }
    Write-Output "$environment federation configured."
}

$verified = & az rest --method get --url "${baseUrl}?api-version=$apiVersion" --output json --only-show-errors 2>&1
if ($LASTEXITCODE -ne 0) { throw 'Unable to verify P-CI federation after provisioning.' }
$credentials = @((($verified -join "`n") | ConvertFrom-Json).value)
foreach ($environment in @('train', 'prod')) {
    $match = @($credentials | Where-Object {
        $_.properties.issuer -ceq 'https://token.actions.githubusercontent.com' -and
        $_.properties.subject -ceq "${subjectPrefix}:environment:$environment" -and
        @($_.properties.audiences).Count -eq 1 -and
        $_.properties.audiences[0] -ceq 'api://AzureADTokenExchange'
    })
    if ($match.Count -ne 1) { throw "$environment federation verification failed." }
}
Write-Output 'PASS: both environment federations verified; unrelated credentials preserved.'
