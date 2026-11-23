param location string = resourceGroup().location
param prefix string = 'amlarclab'
param vmSize string
param sshPublicKey string
param identityIds array
param enableNat bool = false

var tags = {
  purpose: 'aml-arc-lab'
  environment: 'lab'
}

resource natIp 'Microsoft.Network/publicIPAddresses@2026-07-01' = if (enableNat) {
  name: '${prefix}-nat-ip'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
  }
}

resource nat 'Microsoft.Network/natGateways@2026-07-01' = if (enableNat) {
  name: '${prefix}-nat'
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: natIp!.id
      }
    ]
  }
}

resource nsg 'Microsoft.Network/networkSecurityGroups@2026-07-01' = {
  name: '${prefix}-edge-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'DenyInbound'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2026-07-01' = {
  name: '${prefix}-edge-vnet'
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.82.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'edge'
        properties: {
          addressPrefix: '10.82.1.0/24'
          defaultOutboundAccess: false
          privateEndpointNetworkPolicies: 'Disabled'
          networkSecurityGroup: {
            id: nsg.id
          }
          natGateway: enableNat ? {
            id: nat!.id
          } : null
        }
      }
    ]
  }
}

resource onboarding 'Microsoft.ManagedIdentity/userAssignedIdentities@2024-11-30' = {
  name: '${prefix}-arc-onboarding'
  location: location
  tags: tags
}

resource nic 'Microsoft.Network/networkInterfaces@2026-07-01' = {
  name: '${prefix}-edge-nic'
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'private'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: '${vnet.id}/subnets/edge'
          }
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2026-04-01' = {
  name: '${prefix}-edge'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: union({
      '${onboarding.id}': {}
    }, toObject(identityIds, id => id, id => {}))
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: '${prefix}-edge'
      adminUsername: 'labadmin'
      customData: base64(loadTextContent('../../scripts/edge/network-probe.cloud-init.yml'))
      linuxConfiguration: {
        disablePasswordAuthentication: true
        provisionVMAgent: true
        ssh: {
          publicKeys: [
            {
              path: '/home/labadmin/.ssh/authorized_keys'
              keyData: sshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        diskSizeGB: 128
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
        deleteOption: 'Delete'
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
          properties: {
            deleteOption: 'Delete'
          }
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
}

resource shutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vm.name}'
  location: location
  tags: tags
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: {
      time: '1900'
    }
    timeZoneId: 'FLE Standard Time'
    targetResourceId: vm.id
    notificationSettings: {
      status: 'Disabled'
    }
  }
}

output vmName string = vm.name
output vmId string = vm.id
output onboardingClientId string = onboarding.properties.clientId
output onboardingPrincipalId string = onboarding.properties.principalId
output nicId string = nic.id
output subnetId string = '${vnet.id}/subnets/edge'
