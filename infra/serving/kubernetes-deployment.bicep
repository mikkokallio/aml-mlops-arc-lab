param workspaceName string = 'mlw-amlarclab'
param endpointName string = 'amlarclab-aks-1123'
param location string = resourceGroup().location
param sourceGitSha string = '0cfa2c0eab0c716d8ca5922294abdbbf2b187f3b'

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource endpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-10-01' existing = {
  parent: workspace
  name: endpointName
}

resource deployment 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints/deployments@2024-10-01' = {
  parent: endpoint
  name: 'blue'
  location: location
  kind: 'Kubernetes'
  tags: {
    purpose: 'aml-serving-matrix'
    source_git_sha: sourceGitSha
  }
  sku: {
    name: 'Default'
    capacity: 1
  }
  properties: {
    endpointComputeType: 'Kubernetes'
    model: '${workspace.id}/models/campaign-m3-synthetic-proof/versions/2'
    environmentId: '${workspace.id}/environments/campaign-portable-serving/versions/0cfa2c0eab0c'
    instanceType: 'lab-cpu'
    environmentVariables: {
      MODEL_VERSION: '2'
      SOURCE_GIT_SHA: sourceGitSha
      MODEL_PROVENANCE: '${workspace.id}/models/campaign-m3-synthetic-proof/versions/2'
    }
    containerResourceRequirements: {
      containerResourceRequests: {
        cpu: '500m'
        memory: '1Gi'
      }
      containerResourceLimits: {
        cpu: '1'
        memory: '2Gi'
      }
    }
    scaleSettings: {
      scaleType: 'Default'
    }
    requestSettings: {
      requestTimeout: 'PT60S'
    }
  }
}

output deploymentId string = deployment.id
