param location string = resourceGroup().location
param prefix string = 'amlarclab'

var names = [
  'p-rgc'
  'p-ds'
  'p-ci'
  'compute'
]

resource identities 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = [for name in names: {
  name: '${prefix}-${name}'
  location: location
  tags: {
    purpose: 'aml-arc-lab'
    environment: 'lab'
  }
}]

output identities array = [for (name, index) in names: {
  name: name
  id: identities[index].id
  clientId: identities[index].properties.clientId
  principalId: identities[index].properties.principalId
}]
