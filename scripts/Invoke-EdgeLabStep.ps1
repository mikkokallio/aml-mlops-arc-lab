[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Script,
    [Parameter(Mandatory)][string]$EvidenceName,
    [string]$SourceArchive,
    [ValidatePattern('^[0-9a-f]{40}$')][string]$GitSha,
    [string]$VMName = 'amlarclab-edge',
    [string]$ClusterName = 'arc-amlarclab',
    [string]$ClusterLocation = 'swedencentral',
    [string]$K3sVersion = 'v1.35.9+k3s1',
    [string]$HelmNamespace = 'azureml',
    [string]$HelmRelease = 'azureml'
)

$ErrorActionPreference = 'Stop'
if ([bool]$SourceArchive -ne [bool]$GitSha) {
    throw 'SourceArchive and GitSha must be supplied together.'
}
$directory = Join-Path $PSScriptRoot '..\.local'
$identities = (Get-Content (Join-Path $directory 'rg-amlarclab-id.deployment.json') -Raw | ConvertFrom-Json).properties.outputs.identities.value
$edge = (Get-Content (Join-Path $directory 'rg-amlarclab-edge.deployment.json') -Raw | ConvertFrom-Json).properties.outputs
$ml = (Get-Content (Join-Path $directory 'rg-amlarclab-ml.deployment.json') -Raw | ConvertFrom-Json).properties.outputs
$subscription = ($edge.vmId.value -split '/')[2]
$variables = [ordered]@{
    LAB_SUBSCRIPTION = $subscription
    LAB_VM_NAME = $VMName
    LAB_CLUSTER_NAME = $ClusterName
    LAB_CLUSTER_LOCATION = $ClusterLocation
    LAB_K3S_VERSION = $K3sVersion
    LAB_HELM_NAMESPACE = $HelmNamespace
    LAB_HELM_RELEASE = $HelmRelease
    LAB_ONBOARDING_CLIENT_ID = $edge.onboardingClientId.value
    LAB_RGC_CLIENT_ID = ($identities | Where-Object name -eq 'p-rgc').clientId
    LAB_DS_CLIENT_ID = ($identities | Where-Object name -eq 'p-ds').clientId
    LAB_COMPUTE_ID = ($identities | Where-Object name -eq 'compute').id
    LAB_COMPUTE_CLIENT_ID = ($identities | Where-Object name -eq 'compute').clientId
    LAB_WORKSPACE_ID = $ml.workspaceId.value
    LAB_CLUSTER_ID = "/subscriptions/$subscription/resourceGroups/rg-amlarclab-edge/providers/Microsoft.Kubernetes/connectedClusters/$ClusterName"
    LAB_INSTANCE_TYPES_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot '..\config\instance-types.yml')))
    LAB_TRAIN_CODE_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot '..\src\train.py')))
    LAB_FEATURES_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot '..\config\features.yaml')))
    LAB_REQUIREMENTS_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot '..\requirements.txt')))
    LAB_TRACKING_URI = (Get-Content (Join-Path $directory 'workspace.json') -Raw | ConvertFrom-Json).properties.mlFlowTrackingUri
    LAB_STORAGE_HOST = $ml.storageName.value + '.blob.core.windows.net'
    LAB_VAULT_HOST = ($ml.vaultId.value -split '/')[-1] + '.vault.azure.net'
    LAB_COMPARE_CODE_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'compare_predictions.py')))
    LAB_SCORE_CODE_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $PSScriptRoot 'score_private.py')))
}
if ($SourceArchive) {
    $variables.LAB_JOB_SOURCE_BASE64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $SourceArchive)))
    $variables.LAB_GIT_SHA = $GitSha
}
$prefix = ($variables.GetEnumerator() | ForEach-Object { "export $($_.Key)='$($_.Value)'" }) -join "`n"
$generated = Join-Path $directory "$EvidenceName.sh"
[System.IO.File]::WriteAllText(
    $generated,
    $prefix + "`n" + (Get-Content -LiteralPath $Script -Raw),
    [System.Text.UTF8Encoding]::new($false)
)
& (Join-Path $PSScriptRoot 'Invoke-Edge.ps1') -Script $generated -EvidenceName $EvidenceName -VMName $VMName
