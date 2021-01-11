# Hacking vQFX to support ZTP over management interface (em0)

Follow these steps
1. Create a vQFX VM (just the vQFX RE. These process doesn't require vQFX PFE to run)
2. Login into vQFX RE
3. Delete the file /etc/config/vqfx-10000-factory.conf (which is a symbolic link)
4. create /etc/config/vqfx-10000-factory.conf, with the following content
5. zeroize the device
6. shutdown the VM
7. use the disk image for the vQFX that support ZTP over interface em0


## file /etc/config/vqfx-10000-factory.conf that support ZTP over interface em0
```
   system {
       syslog {
           user * {
               any emergency;
           }
           file messages {
               any notice;
               authorization info;
           }
           file interactive-commands {
               interactive-commands any;
           }
       }
       extensions {
           providers {
               juniper {
                   license-type juniper deployment-scope commercial;
               }
               chef {
                   license-type juniper deployment-scope commercial;
               }
           }
       }
       commit {
           factory-settings {
               reset-virtual-chassis-configuration;
               reset-chassis-lcd-menu;
           }
       }
   }
   chassis {
       auto-image-upgrade;
   }
   interfaces {
       em0 {
           unit 0 {
               family inet {
                   dhcp {
                       vendor-id Juniper-qfx10002-72q;
                   }
               }
           }
       }
       em1 {
           unit 0 {
               family inet {
                   address 169.254.0.2/24;
               }
           }
       }
   }
   forwarding-options {
       storm-control-profiles default {
           all;
       }
   }
   protocols {
       igmp-snooping {
           vlan default;
       }
   }
   vlans {
       default {
           vlan-id 1;
       }
   }
```

