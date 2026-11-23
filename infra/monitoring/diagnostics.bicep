param workspaceName string = 'mlw-amlarclab'
param logWorkspaceName string = 'log-amlarclab'

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: logWorkspaceName
}

resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'lab-training-status'
  scope: workspace
  properties: {
    workspaceId: logs.id
    logAnalyticsDestinationType: 'Dedicated'
    logs: [
      {
        category: 'AmlRunStatusChangedEvent'
        enabled: true
      }
    ]
    metrics: []
  }
}

output diagnosticSettingId string = diagnostics.id
output logWorkspaceId string = logs.id
