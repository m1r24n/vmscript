#!/bin/bash
VM=aos
DISK=aos_server_4.0.0-314.qcow2
virt-install --name ${VM} \
	--disk ./${DISK},device=disk,bus=virtio \
	--ram 32784 --vcpu 4  \
	--os-type linux --os-variant generic \
	--network bridge=lan100,model=virtio \
	--console pty,target_type=serial \
	--noautoconsole \
	--vnc  \
	--hvm --accelerate \
	--virt-type=kvm  \
	--boot hd
