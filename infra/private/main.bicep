param location string = resourceGroup().location
param vnetId string
param subnetId string
param storageId string
param vaultId string
param workspaceId string = ''

var connections = [
  {
    name: 'blob'
    zone: 'privatelink.blob.core.windows.net'
    resourceId: storageId
    groupId: 'blob'
  }
  {
    name: 'file'
    zone: 'privatelink.file.core.windows.net'
    resourceId: storageId
    groupId: 'file'
  }
  {
    name: 'vault'
    zone: 'privatelink.vaultcore.azure.net'
    resourceId: vaultId
    groupId: 'vault'
  }
]

resource zones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for connection in connections: {
  name: connection.zone
  location: 'global'
}]

resource links 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (connection, i) in connections: {
  name: '${zones[i].name}/edge'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}]

resource endpoints 'Microsoft.Network/privateEndpoints@2024-05-01' = [for connection in connections: {
  name: 'pe-amlarclab-${connection.name}'
  location: location
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: connection.name
        properties: {
          privateLinkServiceId: connection.resourceId
          groupIds: [
            connection.groupId
          ]
        }
      }
    ]
  }
}]

resource groups 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = [for (connection, i) in connections: {
  name: '${endpoints[i].name}/default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: connection.name
        properties: {
          privateDnsZoneId: zones[i].id
        }
      }
    ]
  }
}]

output endpointIds array = [for i in range(0, length(connections)): endpoints[i].id]

var workspaceZoneNames = [
  'privatelink.api.azureml.ms'
  'privatelink.notebooks.azure.net'
]

resource workspaceZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zone in workspaceZoneNames: if (!empty(workspaceId)) {
  name: zone
  location: 'global'
}]

resource workspaceLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zone, i) in workspaceZoneNames: if (!empty(workspaceId)) {
  name: '${workspaceZones[i].name}/edge'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}]

resource workspaceEndpoint 'Microsoft.Network/privateEndpoints@2024-05-01' = if (!empty(workspaceId)) {
  name: 'pe-amlarclab-workspace'
  location: location
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'workspace'
        properties: {
          privateLinkServiceId: workspaceId
          groupIds: [
            'amlworkspace'
          ]
        }
      }
    ]
  }
}

resource workspaceZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (!empty(workspaceId)) {
  parent: workspaceEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [for (zone, i) in workspaceZoneNames: {
      name: 'workspace-${i}'
      properties: {
        privateDnsZoneId: workspaceZones[i].id
      }
    }]
  }
}
