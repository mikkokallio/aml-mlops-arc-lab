[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$directory = Join-Path $PSScriptRoot '..\..\.local'
$env:AZURE_EXTENSION_DIR = Join-Path $directory 'az-extensions'
& az extension add --name k8s-extension --version 1.9.5 --yes
if ($LASTEXITCODE -ne 0) { throw 'Pinned extension dependency installation failed.' }
$arguments = @(
    'k8s-extension', 'create',
    '--name', 'azureml',
    '--extension-type', 'Microsoft.AzureML.Kubernetes',
    '--cluster-type', 'connectedClusters',
    '--cluster-name', 'arc-amlarclab',
    '--resource-group', 'rg-amlarclab-edge',
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
    scope = 'Dedicated edge RG; CLI creates and configures the extension Relay dependency'
    reason = 'P-RGC edge-cluster read denial recorded before authorized platform administration'
    exitCode = $exitCode
} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $directory 'admin-actions.jsonl')
$result | Write-Output
if ($exitCode -ne 0) { throw 'AML Kubernetes extension installation failed.' }
