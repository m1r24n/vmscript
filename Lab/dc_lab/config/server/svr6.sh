#!/bin/bash
VM=svr6
DISK=${VM}.img
virt-install --name ${VM} \
	--disk ./${DISK},device=disk,bus=virtio \
	--ram 256 --vcpu 1  \
	--os-type linux --os-variant generic \
	--network bridge=sw2p10,model=e1000 \
	--console pty,target_type=serial \
	--noautoconsole \
	--vnc  \
	--hvm --accelerate \
	--virt-type=kvm  \
	--boot hd
