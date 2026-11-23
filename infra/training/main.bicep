param location string = resourceGroup().location
param workspaceName string = 'mlw-amlarclab'
param computeName string = 'cpu-training'
param subnetId string
param vmSize string = 'Standard_DS3_v2'

resource workspace 'Microsoft.MachineLearningServices/workspaces@2026-09-01' existing = {
  name: workspaceName
}

resource compute 'Microsoft.MachineLearningServices/workspaces/computes@2026-09-01' = {
  parent: workspace
  name: computeName
  location: location
  tags: {
    purpose: 'aml-arc-lab'
    environment: 'lab'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    computeType: 'AmlCompute'
    properties: {
      vmSize: vmSize
      vmPriority: 'Dedicated'
      osType: 'Linux'
      enableNodePublicIp: false
      remoteLoginPortPublicAccess: 'Disabled'
      subnet: {
        id: subnetId
      }
      scaleSettings: {
        minNodeCount: 0
        maxNodeCount: 1
        nodeIdleTimeBeforeScaleDown: 'PT2M'
      }
    }
  }
}

output computeId string = compute.id
output computePrincipalId string = compute.identity.principalId
