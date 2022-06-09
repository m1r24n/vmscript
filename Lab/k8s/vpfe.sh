virt-install --name vpfe \
  --disk /home/irzan/vm/dcgw/dcgw/vFPC-20220223.img,device=disk,format=qcow2  \
  --memory=2048 --vcpu 3 \
  --osinfo linux2020  \
  --network bridge=lan100,model=virtio  \
  --network bridge=Intdcgw,model=virtio  \
  --network bridge=br1,model=virtio  \
  --console pty,target_type=serial --noautoconsole  --graphics vnc,password=pass01,listen=0.0.0.0 --virt-type=kvm --boot hd


