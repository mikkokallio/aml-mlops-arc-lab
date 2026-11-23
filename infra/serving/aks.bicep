param location string = resourceGroup().location
param clusterName string = 'aks-amlarclab-smoke'
param kubernetesVersion string
param sshPublicKey string

var tags = {
  purpose: 'aml-serving-matrix'
  environment: 'disposable'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: '${clusterName}-control'
  location: location
  tags: tags
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' existing = {
  name: 'amlarclab-edge-vnet/serving-aks'
}

resource networkRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(subnet.id, identity.id, 'Network Contributor')
  scope: subnet
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4d97b98b-1d4f-4787-a291-c67834d212e7')
  }
}

resource cluster 'Microsoft.ContainerService/managedClusters@2025-01-01' = {
  name: clusterName
  location: location
  tags: tags
  sku: {
    name: 'Base'
    tier: 'Free'
  }
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    kubernetesVersion: kubernetesVersion
    dnsPrefix: clusterName
    nodeResourceGroup: '${clusterName}-nodes'
    disableLocalAccounts: false
    enableRBAC: true
    apiServerAccessProfile: {
      enablePrivateCluster: true
      enablePrivateClusterPublicFQDN: false
    }
    agentPoolProfiles: [
      {
        name: 'system'
        count: 1
        vmSize: 'Standard_D4s_v5'
        osType: 'Linux'
        osSKU: 'Ubuntu'
        osDiskSizeGB: 64
        type: 'VirtualMachineScaleSets'
        mode: 'System'
        vnetSubnetID: subnet.id
        enableNodePublicIP: false
      }
    ]
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      podCidr: '10.244.0.0/16'
      serviceCidr: '10.245.0.0/16'
      dnsServiceIP: '10.245.0.10'
      outboundType: 'userAssignedNATGateway'
      loadBalancerSku: 'standard'
    }
    linuxProfile: {
      adminUsername: 'labadmin'
      ssh: {
        publicKeys: [
          {
            keyData: sshPublicKey
          }
        ]
      }
    }
  }
  dependsOn: [
    networkRole
  ]
}

output clusterId string = cluster.id
output controlIdentityId string = identity.id
output networkRoleId string = networkRole.id
