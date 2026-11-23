param workspaceName string = 'mlw-amlarclab'
param logWorkspaceName string = 'log-amlarclab'
param location string = resourceGroup().location

resource workspace 'Microsoft.MachineLearningServices/workspaces@2024-10-01' existing = {
  name: workspaceName
}

resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' existing = {
  name: logWorkspaceName
}

resource failedJobAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'aml-training-failed'
  location: location
  kind: 'LogAlert'
  tags: {
    purpose: 'aml-arc-lab'
    environment: 'lab'
  }
  properties: {
    displayName: 'AML training job failed'
    description: 'Azure-only lab alert. Customer notification preferences must be explicitly collected before rollout.'
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
          query: 'AmlRunStatusChangedEvent | where _ResourceId =~ \'${workspace.id}\' | where Status == \'Failed\' | project TimeGenerated, RunId, Status, _ResourceId'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          resourceIdColumn: '_ResourceId'
          dimensions: [
            {
              name: 'RunId'
              operator: 'Include'
              values: [
                '*'
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

output alertRuleId string = failedJobAlert.id
