[CmdletBinding()]
param(
    [string]$ClusterName = 'arc-amlarclab',
    [string]$ResourceGroup = 'rg-amlarclab-edge'
)

$ErrorActionPreference = 'Stop'
$directory = Join-Path $PSScriptRoot '..\..\.local'
$env:AZURE_EXTENSION_DIR = Join-Path $directory 'az-extensions'
$installedVersion = & az extension show --name k8s-extension --query version --output tsv
if ($LASTEXITCODE -ne 0 -or $installedVersion -ne '1.9.5') {
    throw 'Install the required task-local k8s-extension version 1.9.5 before continuing.'
}
$arguments = @(
    'k8s-extension', 'create',
    '--name', 'azureml',
    '--extension-type', 'Microsoft.AzureML.Kubernetes',
    '--cluster-type', 'connectedClusters',
    '--cluster-name', $ClusterName,
    '--resource-group', $ResourceGroup,
    '--scope', 'cluster',
    '--release-namespace', 'azureml',
    '--auto-upgrade-minor-version', 'true',
    '--configuration-settings', 'enableInference=True', 'enableTraining=False',
    'inferenceRouterServiceType=nodePort', 'allowInsecureConnections=True',
    'inferenceRouterHA=False',
    '--output', 'json'
)
$result = & az @arguments 2>&1
$exitCode = $LASTEXITCODE
$result | Set-Content -LiteralPath (Join-Path $directory 'aml-extension-install.log')
[ordered]@{
    timestamp = (Get-Date).ToUniversalTime().ToString('o')
    persona = 'Owner'
    command = 'az ' + ($arguments -join ' ')
    permission = 'Microsoft.KubernetesConfiguration/extensions/write; Microsoft.Relay/namespaces/write; Microsoft.Authorization/roleAssignments/write'
    scope = "$ResourceGroup / $ClusterName; CLI creates and configures the extension Relay dependency"
    reason = 'P-RGC edge-cluster read denial recorded before authorized platform administration'
    exitCode = $exitCode
} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
$result | Write-Output
if ($exitCode -ne 0) { throw 'AML Kubernetes extension installation failed.' }
