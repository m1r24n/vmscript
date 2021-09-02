# Script to Deploy Junos VM on KVM, next-gen version
release 0.2

## Overview
This script is used to deploy Junos VM (vMX, vQFX, vSRX, and vRR) on KVM, which is useful to create network topology for testing purposes.

This script has been tested on the Ubuntu Linux 18.04 and Centos 7.7)

## Caveat
Some caveats on using this script
1. pynetlinux library
	- to install pytnetlinux library, clone the source from github
	- before seting up the library, make sure that all the necessary development tool and library are installed (such as compiler, libvirt-development-library, etc)

2. setting MTU on centos.

Unfortunately the QEMU library on centos is the old one and it doesn't support MTU setting.
To fix this, you can either install the latest library or edit junos_vm_xml.py, by commenting line that set the mtu :

		# mtu=ET.Element("mtu",{'size':MTU})
		# i.insert(0,mtu)

## Requirement
This script requires the following :
- Python3 (this script requires Python3)
- PyEZ (to install use `pip3 install junos-eznc`)
- passlib library (to install use `pip3 install passlib`)
- pexpect library (to install use `pip3 install pexpect`)
- libvirt python library
- dnsmasq server as DHCP server
- tftp server to provide initial configuration
- pynetlinux library https://github.com/rlisagor/pynetlinux

## Recompile linux kernel on the KVM host to allow LLDP and LACP frames to pass through

Reference : [how to compile kernel on debian](https://wiki.debian.org/BuildADebianKernelPackage)

Reference : [how to compile kernel on ubuntu](https://wiki.ubuntu.com/Kernel/BuildYourOwnKernel)

By default, linux bridge will not allow LLDP and LACP frames to pass through. 

To allow LLDP and LACP frames to be sent and received by the VM, the linux kernel of the KVM host must be recompile

Do the following steps to recompile the linux kernel.
1. Install the linux kernel and the necessary development tools to compile the kernel.2
2. Under linux kernel source directory, edit file  **<kernel_source>/net/bridge/br_private.h**, and look for the following entry

		#define BR_GROUPFWD_RESTRICTED

	and change the value to 

		#define BR_GROUPFWD_RESTRICTED 0x0000u

3. Copy kernel configuration file from director /boot into linux kernel source directory as file .config
4. Compile the linux kernel and install it
5. Reboot into the new kernel


## Set the hugepages on kvm host
1. on ubuntu/debian, edit file /etc/default/grub, and add the following entry

		GRUB_CMDLINE_LINUX="default_hugepagesz=1G hugepagesz=1G hugepages=48G"

2. Set the maximum hugepages according to the maximum RAM that you have on the KVM host. For example, I set the maximum hugepages memory to 48G on the server with 64G of RAM

3. recreate the grub configuration file. On ubuntu/debian, you can do the following

		sudo grub-mkconfig -o /boot/grub/grub.cfg

4. Reboot the KVM host to enable hugepages memory

## Junos VM image
For VMX, use the official vMX release from juniper, **[vmx](http://www.juniper.net/support/downloads/?p=vmx#sw)**. Download the KVM version, uncompres and untar the file, and get four (4) files from image directory (three files for RE are`junos-vmx-***.qcow2`, `vmxhdd.img` and `metadata-usb-re.img`, and one file for PFE is `vFPC-***.img`)

For VSRX,use the official vSRX release from juniper, **[vsrx](http://www.juniper.net/support/downloads/?p=vsrx#sw)**. Download the KVM Version.

For vRR, use the official vRR release from juniper, **[vrr](http://www.juniper.net/support/downloads/?p=vrr#sw)**. Download the KVM version (format `img`)

For vQFX use the vQFX trial from juniper, **[vqfx](http://www.juniper.net/support/downloads/?p=vqfxeval#sw)**.
By default vQFX image only support ZTP on interface xe-0/0/N. it doesn't support ZTP on management interface (em0). To make vQFX image able to do ZTP over em0 interface, please follow this instruction **[vqfx_hacked](vqfx_hacked.md)**


## Script Files

This tool consist of the following script
- **[junos_vm.py](junos_vm.py)**
- **[junos_vm_xml.py](junos_vm_xml.py)**
- **[vmm.py](vmm.py)**

## junos_vm.py
This script is the library with functions used by the other scripts (`vmm.py`)

## vmm.py
This script will read the definition file (a yaml file), which contain the following information :
- image files used by Junos VM
- the source directory for the Junos VM's image
- destination folder where the images will be stored
- the VMs definition (such as type : vMX/vSRX/vQFX/vRR, interfaces used by VM)
- bridge used for connection between VMs and its type (lb : for linuxbridge, and ovs: for openvswitch)
- IP address of management interface of each VM


This script will do the following (depend on the argument given to the script)
- argument `addbr`,  this script will create bridges on linux host (bridge which is used for connecting VMs), this script must be run with sudo
- argument `delbr`, this script will delete bridges on linux host, this script must be run with sudo
- argument `definevm`, this script will create VM instance (domain), copy VM's image files from source to destination directory, create `dnsmasq.conf` for the DNSMASQ DHCP server, and initial configuration for each virtual junos instances. 
- argument `undefinevm` this script will delete VM's image files and remove VM instances (domain) from the hypervisor
- argument `start <vm_name | all>`, this script will start start VMs instances on hypervisor
- argument `stop <vm_name | all>`, this script will start stop VMs instances on hypervisor

## How to run the script
1. Create a working directory (for example ~/lab1), and create the definition file 
2. Copy the Junos VM images into the source directory (please refer to the definition file for this)
3. Run script to create the bridge, for example **sudo vmm.py -c lab.yaml addbr**
4. Run script to create VM instances and copy the VM image, for example **vmm.py -c lab.yaml definevm**
5. Run script to run the VM intances. it can be **vmm.py -c lab.yaml start**, to start all instances at the same time or it can be **vmm.py -c lab.yaml start <node_name>**, to start the instance one by one
6. Wait for 5 to 10 minutes (depend on how many Junos VMs that you define in your topology) for the VMs to be up and running
7. Run **vmm.py -c lab.yaml init_vm** to configure management ip address, login information, and enabling ssh/netconf on the junos VM.
8. To verify, try to access the console port of the Junos VMs (if you get `login:` prompt, it means the VM is up and running) or ping the management ip address of the Junos VM
9. To stop the VM instances,  it can be **vmm.py -c lab.yaml stop all**, to stop all instances at the same time or it can be **vmm.py -c lab.yaml stop <node_name>**, to stop the instance one by one
19. To remove the VM instances and VM image files, run **vmm.py -c lab.yaml undefinevm**
11. To remove the bridges, run **sudo vmm.py -c lab.yaml delbr**


## Basic command
- `virsh list` : to display the running VMs
- `virsh console <id>` or `virsh console <name>` to access the VM through serial console ... To exit the console access, press button `ctrl` and  `]`
- `brctl show` or `brctl show <bridge name>` : to display bridge that has been configured on the linux host


