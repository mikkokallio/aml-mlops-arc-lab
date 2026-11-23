param location string = resourceGroup().location
param prefix string = 'amlarclab'

var suffix = uniqueString(subscription().subscriptionId, resourceGroup().id)
var tags = {
  purpose: 'aml-arc-lab'
  environment: 'lab'
}

resource storage 'Microsoft.Storage/storageAccounts@2025-06-01' = {
  name: 'st${prefix}${suffix}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'None'
      resourceAccessRules: [
        {
          tenantId: tenant().tenantId
          resourceId: resourceId('Microsoft.MachineLearningServices/workspaces', 'mlw-${prefix}')
        }
      ]
    }
    defaultToOAuthAuthentication: true
    accessTier: 'Hot'
  }
}

resource vault 'Microsoft.KeyVault/vaults@2025-05-01' = {
  name: 'kv-${prefix}-${take(suffix, 8)}'
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      ipRules: []
      virtualNetworkRules: []
    }
    accessPolicies: []
  }
}

resource registry 'Microsoft.ContainerRegistry/registries@2025-04-01' = {
  name: 'cr${prefix}${suffix}'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    anonymousPullEnabled: false
    publicNetworkAccess: 'Enabled'
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2025-02-01' = {
  name: 'log-${prefix}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: 1
    }
  }
}

resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${prefix}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    DisableLocalAuth: true
  }
}

resource workspace 'Microsoft.MachineLearningServices/workspaces@2026-09-01' = {
  name: 'mlw-${prefix}'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'AML Arc lab'
    description: 'Dedicated reproducible Arc inference lab'
    storageAccount: storage.id
    keyVault: vault.id
    containerRegistry: registry.id
    applicationInsights: insights.id
    publicNetworkAccess: 'Enabled'
    systemDatastoresAuthMode: 'identity'
  }
}

output workspaceName string = workspace.name
output workspaceId string = workspace.id
output workspacePrincipalId string = workspace.identity.principalId
output storageId string = storage.id
output storageName string = storage.name
output vaultId string = vault.id
output registryId string = registry.id
output registryName string = registry.name
