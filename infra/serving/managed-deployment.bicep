param workspaceName string = 'mlw-amlarclab'
param endpointName string
param deploymentName string = 'blue'
param modelName string = 'campaign-m3-synthetic-proof'
@allowed([
  '1'
  '2'
])
param modelVersion string = '1'
param environmentVersion string
param image string
param sourceGitSha string
param instanceType string = 'Standard_DS2_v2'
param location string = resourceGroup().location

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource endpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-10-01' existing = {
  parent: workspace
  name: endpointName
}

resource environment 'Microsoft.MachineLearningServices/workspaces/environments@2024-10-01' existing = {
  parent: workspace
  name: 'campaign-portable-serving'
}

resource version 'Microsoft.MachineLearningServices/workspaces/environments/versions@2024-10-01' = {
  parent: environment
  name: environmentVersion
  properties: {
    description: 'Prebuilt immutable image; no runtime package installation.'
    image: image
    autoRebuild: 'Disabled'
    osType: 'Linux'
    tags: {
      git_sha: sourceGitSha
    }
    inferenceConfig: {
      livenessRoute: {
        port: 8080
        path: '/health'
      }
      readinessRoute: {
        port: 8080
        path: '/health'
      }
      scoringRoute: {
        port: 8080
        path: '/score'
      }
    }
  }
}

resource deployment 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints/deployments@2024-10-01' = {
  parent: endpoint
  name: deploymentName
  location: location
  kind: 'Managed'
  tags: {
    purpose: 'aml-serving-matrix'
    source_git_sha: sourceGitSha
  }
  sku: {
    name: 'Default'
    capacity: 1
  }
  properties: {
    endpointComputeType: 'Managed'
    description: 'Private prebuilt serving image and registered model; disposable lifecycle test.'
    model: '${workspace.id}/models/${modelName}/versions/${modelVersion}'
    environmentId: version.id
    instanceType: instanceType
    egressPublicNetworkAccess: 'Disabled'
    appInsightsEnabled: false
    environmentVariables: {
      MODEL_VERSION: modelVersion
      SOURCE_GIT_SHA: sourceGitSha
      MODEL_PROVENANCE: '${workspace.id}/models/${modelName}/versions/${modelVersion}'
      PROBE_PACKAGE_INDEX: '1'
    }
    scaleSettings: {
      scaleType: 'Default'
    }
    requestSettings: {
      requestTimeout: 'PT60S'
      maxConcurrentRequestsPerInstance: 1
    }
    livenessProbe: {
      initialDelay: 'PT30S'
      period: 'PT10S'
      timeout: 'PT2S'
      failureThreshold: 30
    }
    readinessProbe: {
      initialDelay: 'PT30S'
      period: 'PT10S'
      timeout: 'PT2S'
      failureThreshold: 30
    }
  }
}

output deploymentId string = deployment.id
