param workspaceName string = 'mlw-amlarclab'
param endpointName string = 'amlarclab-aks-1123'
param computeName string = 'aks-smoke'
param identityId string
param location string = resourceGroup().location

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource endpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-10-01' = {
  parent: workspace
  name: endpointName
  location: location
  kind: 'Kubernetes'
  tags: {
    purpose: 'aml-serving-matrix'
    environment: 'disposable'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityId}': {}
    }
  }
  properties: {
    description: 'Disposable native AKS private NodePort smoke test.'
    authMode: 'Key'
    compute: '${workspace.id}/computes/${computeName}'
  }
}

output endpointId string = endpoint.id
