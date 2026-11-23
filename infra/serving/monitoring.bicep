param workspaceName string = 'mlw-amlarclab'
param endpointName string
param logWorkspaceName string = 'log-amlarclab'
param enableAlert bool = false
param failureRequestId string = 'aml-serving-matrix-negative-1123'
param location string = resourceGroup().location

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource endpoint 'Microsoft.MachineLearningServices/workspaces/onlineEndpoints@2024-10-01' existing = {
  parent: workspace
  name: endpointName
}

resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: logWorkspaceName
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'lab-serving-matrix'
  scope: endpoint
  properties: {
    workspaceId: logs.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        category: 'AmlOnlineEndpointTrafficLog'
        enabled: true
      }
      {
        category: 'AmlOnlineEndpointConsoleLog'
        enabled: true
      }
      {
        category: 'AmlOnlineEndpointEventLog'
        enabled: true
      }
    ]
    metrics: []
  }
}

resource alert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = if (enableAlert) {
  name: 'aml-serving-matrix-failure'
  location: location
  kind: 'LogAlert'
  tags: {
    purpose: 'aml-serving-matrix'
    environment: 'disposable'
  }
  properties: {
    displayName: 'Controlled AML inference failure'
    description: 'Disposable Azure-only proof for one deliberately invalid inference request; not a production alert policy.'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT1M'
    windowSize: 'PT30M'
    autoMitigate: true
    skipQueryValidation: false
    scopes: [
      logs.id
    ]
    criteria: {
      allOf: [
        {
          query: 'AmlOnlineEndpointTrafficLog | where EndpointName == \'${endpointName}\' | where XMSClientRequestId == \'${failureRequestId}\' | where ResponseCode >= 400 or ModelStatusCode >= 400 | project TimeGenerated, EndpointName, XMSClientRequestId, ResponseCode, ModelStatusCode, _ResourceId'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          resourceIdColumn: '_ResourceId'
          dimensions: [
            {
              name: 'XMSClientRequestId'
              operator: 'Include'
              values: [
                failureRequestId
              ]
            }
          ]
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: []
    }
  }
}
