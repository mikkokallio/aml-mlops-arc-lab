param location string = resourceGroup().location
param groupName string = 'aci-amlarclab-smoke'
param subnetId string
param identityId string
param image string
param registryServer string

resource group 'Microsoft.ContainerInstance/containerGroups@2023-05-01' = {
  name: groupName
  location: location
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
    osType: 'Linux'
    restartPolicy: 'Always'
    subnetIds: [
      {
        id: subnetId
      }
    ]
    imageRegistryCredentials: [
      {
        server: registryServer
        identity: identityId
      }
    ]
    ipAddress: {
      type: 'Private'
      ports: [
        {
          port: 8080
          protocol: 'TCP'
        }
      ]
    }
    containers: [
      {
        name: 'model'
        properties: {
          image: image
          environmentVariables: [
            {
              name: 'MODEL_VERSION'
              value: '2'
            }
          ]
          ports: [
            {
              port: 8080
              protocol: 'TCP'
            }
          ]
          resources: {
            requests: {
              cpu: 1
              memoryInGB: 2
            }
          }
        }
      }
    ]
  }
}

output groupId string = group.id
output privateIp string = group.properties.ipAddress.ip
