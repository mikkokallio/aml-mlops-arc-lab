param workspaceName string = 'mlw-amlarclab'
param endpointName string
param identityId string
param location string = resourceGroup().location

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource endpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-10-01' = {
  parent: workspace
  name: endpointName
  location: location
  kind: 'Managed'
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
    description: 'Disposable private managed serving lifecycle test.'
    authMode: 'Key'
    publicNetworkAccess: 'Disabled'
  }
}

output endpointId string = endpoint.id
