param vnetName string = 'amlarclab-edge-vnet'
param natName string = 'amlarclab-nat'
param subnetName string
param addressPrefix string
param delegation string = ''

resource vnet 'Microsoft.Network/virtualNetworks@2024-05-01' existing = {
  name: vnetName
}

resource nat 'Microsoft.Network/natGateways@2024-05-01' existing = {
  name: natName
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = {
  parent: vnet
  name: subnetName
  properties: {
    addressPrefix: addressPrefix
    defaultOutboundAccess: false
    natGateway: {
      id: nat.id
    }
    delegations: empty(delegation) ? [] : [
      {
        name: 'serving-delegation'
        properties: {
          serviceName: delegation
        }
      }
    ]
  }
}

output subnetId string = subnet.id
