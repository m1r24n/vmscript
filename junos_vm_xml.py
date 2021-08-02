import os
import xml.etree.ElementTree as ET
import pynetlinux
import subprocess
import libvirt
import traceback
import shutil

# from jnpr.junos import Device
# from jnpr.junos.utils.config import Config
from passlib.hash import md5_crypt

MTU='9192'
VNC_PASSWORD='foobar'

def virtinstall2xml(virtinstallCMD,mgmt):
	# root=tree.getroot()
	result1=os.popen(virtinstallCMD).read()
	root=ET.fromstring(result1)
	j_index=0	
	for i in root:
		if i.tag=='uuid':
			remove_index=j_index
		j_index +=1
	remove1=root.getchildren()[remove_index]
	root.remove(remove1)
	for i in root.findall("./devices/interface"):
		j_index=0	
		for j in i:
			if j.tag=='mac':
				remove_index=j_index
			j_index += 1
		for j in i:
			if j.tag=='source':
				if j.attrib['bridge']!=mgmt:
					remove1=i.getchildren()[remove_index]
					i.remove(remove1)
					mtu=ET.Element("mtu",{'size':MTU})
					i.insert(0,mtu)
					break
			j_index+=1
	# ET.dump(root)
	return ET.tostring(root)
	#print(txt1)

def intfcmd(node,d1):
	lab_name = d1['lab_name']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	cmd_list=""
	exist_bridge=d1['exist_bridge']
	model="e1000"
	if d1['nodes'][node]['type'] == 'vmx':
		model="virtio"

	for i in interfaces:
		# bridge_name = lab_name + "-" + d1['nodes'][node]['interfaces'][i] 
		ovs=False
		if 'bridge' in d1['nodes'][node]['interfaces'][i]:
			bridge_name = d1['nodes'][node]['interfaces'][i]['bridge']
			if 'brtype' in d1['nodes'][node]['interfaces'][i]:
				if d1['nodes'][node]['interfaces'][i]['brtype']=='ovs':
					ovs=True
				
			'''
			if d1['nodes'][node]['interfaces'][i]['bridge'] in exist_bridge:
				bridge_name = d1['nodes'][node]['interfaces'][i]['bridge']
			else:
				bridge_name = lab_name + "-" + d1['nodes'][node]['interfaces'][i]['bridge']
			'''
			target_name = lab_name + "_" + node + "_" + i.split('-')[0] + "_" + i.split('-')[1].split('/')[2]
			if ovs:
				cmd_list += "--network bridge=" + bridge_name + ",model=" + model + ",target=" + target_name + ",virtualport_type=openvswitch "
			else:
				cmd_list += "--network bridge=" + bridge_name + ",model=" + model + ",target=" + target_name + " "

	return cmd_list

def mgmt_bridge(d1):
	'''
	if 'exist_bridge' in d1.keys():
		eb=d1['exist_bridge']
	else:
		eb=['']
	'''
	retval = d1['mgmt']['intf']
	'''
	if d1['mgmt']['intf'] in eb:
		retval = d1['mgmt']['intf']
	else:
		retval = d1['lab_name'] + "-" + d1['mgmt']['intf']
	'''
	return retval


def create_vpfe_vqfx_xml(node,d1): 
	lab_name = d1['lab_name']
	pfe_file = d1['files']['vqfx']['pfe_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	mgmt = d1['mgmt']['intf']
	# mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vpfe-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + pfe_file +",device=disk,bus=ide "
	#cmd_head +="--ram 1536 --vcpu 1 --os-type linux --os-variant generic "
	#cmd_head +="--ram 1536 --vcpu 1 "
	cmd_head +="--memory=2048,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	cmd_head +="--network bridge=" + mgmt+",model=e1000 "
	# cmd_head +="--network bridge=" + lab_name +"Int" + node + ",model=e1000 " 
	cmd_head +="--network bridge=Int" + node + ",model=e1000 " 
	cmd_tail="--console pty,target_type=serial --noautoconsole --hvm --accelerate --graphics vnc,password=" + VNC_PASSWORD + ",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml
	
def create_vcp_vqfx_xml(node,d1): 
	lab_name = d1['lab_name']
	re_file = d1['files']['vqfx']['re_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	# mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	mgmt = d1['mgmt']['intf']
	# mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vcp-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + re_file +",device=disk,bus=ide "
	# cmd_head +="--ram 2048 --vcpu 1 --os-type linux --os-variant generic "
	#cmd_head +="--ram 2048 --vcpu 1 "
	cmd_head +="--memory=2048,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	#cmd_head +="--sysinfo smbios,bios.vendor=Juniper,system.manufacturer=Juniper,system.version=0.1.0,system.product=vQFX "
	# cmd_head +="--ram 1024 --vcpu 1 --os-type linux --os-variant generic "
	if 'mac' in d1['nodes'][node]['mgmt'].keys():
		cmd_head +="--network bridge=" + mgmt+",model=e1000,mac=" + d1['nodes'][node]['mgmt']['mac'] + " " 
	else:
		cmd_head +="--network bridge=" + mgmt+",model=e1000 " 
	#cmd_head +="--network bridge=" + lab_name +"Int" + node + ",model=e1000 " 
	#cmd_head +="--network bridge=" + lab_name +"Int" + node +",model=e1000 " 
	cmd_head +="--network bridge=Int" + node + ",model=e1000 " 
	cmd_head +="--network bridge=Int" + node +",model=e1000 " 
	cmd_tail="--console pty,target_type=serial --noautoconsole --hvm --accelerate --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml


def create_vsrx_xml(node,d1):
	lab_name = d1['lab_name']
	vsrx_file = d1['files']['vsrx']['re_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	# mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	#mgmt = mgmt_bridge(d1)
	mgmt = d1['mgmt']['intf']
	cmd_head="virt-install --name " + lab_name + "-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + vsrx_file +",device=disk,bus=ide,size=16,format=qcow2 "
	#cmd_head +="--ram 4096 --vcpu 2 --os-type linux --os-variant rhel7  --arch=x86_64 "
	#cmd_head +="--ram 4096 --vcpu 2 "
	cmd_head +="--memory=4096,hugepages=yes --memorybacking hugepages=yes --vcpu 2 "
	cmd_head +="--cpu SandyBridge,+pbe,+tm2,+est,+vmx,+osxsave,+smx,+ss,+ds,+vme,+dtes64,+monitor,+ht,+dca,+pcid,+tm,+pdcm,+pdpe1gb,+ds_cpl,+xtpr,+acpi,-invtsc "
	if 'mac' in d1['nodes'][node]['mgmt'].keys():
		cmd_head +="--network bridge=" + mgmt+",model=e1000,mac=" + d1['nodes'][node]['mgmt']['mac'] + " " 
	else:
		cmd_head +="--network bridge=" + mgmt+",model=e1000 " 
	cmd_tail="--console pty,target_type=serial --noautoconsole --hvm --accelerate --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml

def create_vmx_xml(node, d1):
	lab_name = d1['lab_name']
	re_file = "/" + d1['files']['vmx']['nested']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	mgmt = d1['mgmt']['intf']
	cmd_head="virt-install --name " + lab_name + "-vmx-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + re_file +",device=disk,bus=ide,format=qcow2 "
	cmd_head +="--memory=4096,hugepages=yes --memorybacking hugepages=yes --vcpu 4 "
	#cmd_head +="--cpu host-passthrough "
	cmd_head +="--cpu SandyBridge,+erms,+smep,+fsgsbase,+pdpe1gb,+rdrand,+f16c,+osxsave,+dca,+pcid,+pdcm,+xtpr,+tm2,+est,+smx,+vmx,+ds_cpl,+monitor,+dtes64,+pbe,+tm,+ht,+ss,+acpi,+ds,+vme "
	#cmd_head +="--sysinfo smbios,bios.vendor=Juniper,system.manufacturer=Juniper,system.version=0.1.0,system.product=vMX "
	if 'mac' in d1['nodes'][node]['mgmt'].keys():
		cmd_head +="--network bridge=" + mgmt+",model=virtio,mac=" + d1['nodes'][node]['mgmt']['mac'] + " " 
	else:
		cmd_head +="--network bridge=" + mgmt+",model=virtio " 
	cmd_tail="--console pty,target_type=serial --noautoconsole  --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd_list=""
	cmd1 = cmd_head + cmd_list + cmd_tail
	xml=virtinstall2xml(cmd1,mgmt)
	return xml

def create_vcp_vmx_xml(node, d1,re):
	lab_name = d1['lab_name']
	re_file = d1['files']['vmx']['re_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	# mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	mgmt = d1['mgmt']['intf']
	#mgmt = mgmt_bridge(d1)	
	if re=="-1":
		vcp_name = "-vcp-"
		re_dir = "/"
		usb_image = node + re_dir + "metadata-usb-re.img,device=disk,bus=ide,format=raw "
	elif re=="0":
		vcp_name = "-vcp0-"
		re_dir = "/re0/"
		usb_image = node + re_dir + "metadata-usb-re0.img,device=disk,bus=ide,format=raw "
	elif re=="1":
		vcp_name = "-vcp1-"
		re_dir = "/re1/"
		usb_image = node + re_dir + "metadata-usb-re1.img,device=disk,bus=ide,format=raw "

	cmd_head="virt-install --name " + lab_name + vcp_name + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + re_dir + re_file +",device=disk,bus=ide,format=qcow2 "
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + re_dir + "vmxhdd.img,device=disk,bus=ide,format=qcow2 "
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + usb_image
	# cmd_head +="--ram 1024 --vcpu 1 --os-type linux --os-variant rhel7  --arch=x86_64 "
	#cmd_head +="--ram 1024 --vcpu 1 "
	cmd_head +="--memory=1024,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	#cmd_head +="--sysinfo smbios,bios.vendor=Juniper,system.manufacturer=Juniper,system.version=0.1.0,system.product=vMX "
	if 'mac' in d1['nodes'][node]['mgmt'].keys():
		cmd_head +="--network bridge=" + mgmt+",model=virtio,mac=" + d1['nodes'][node]['mgmt']['mac'] + " " 
	else:
		cmd_head +="--network bridge=" + mgmt+",model=virtio " 
	
	# cmd_head +="--network bridge=" + lab_name + "Int" + node+",model=virtio "
	cmd_head +="--network bridge=Int" + node+",model=virtio "
	cmd_tail="--console pty,target_type=serial --noautoconsole  --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd_list=""
	cmd1 = cmd_head + cmd_list + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml

def create_vpfe_vmx_xml(node, d1):
	lab_name = d1['lab_name']
	pfe_file = d1['files']['vmx']['pfe_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	# mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	mgmt = d1['mgmt']['intf']
	#mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vpfe-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + pfe_file +",device=disk,bus=ide,format=qcow2 "
	# cmd_head +="--ram 3072 --vcpu 4 --os-type linux --os-variant rhel7  --arch=x86_64 "
	#cmd_head +="--ram 3072 --vcpu 4 "
	cmd_head +="--memory=3072,hugepages=yes --memorybacking hugepages=yes --vcpu 4 "
	cmd_head +="--cpu host-passthrough "
	cmd_head +="--network bridge=" + mgmt+",model=virtio "
	# cmd_head +="--network bridge=" + lab_name+"Int" + node +",model=virtio "
	cmd_head +="--network bridge=Int" + node +",model=virtio "
	cmd_tail="--console pty,target_type=serial --noautoconsole  --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml

def create_vrr_xml(node, d1):
	lab_name = d1['lab_name']
	vrr_file = d1['files']['vrr']['re_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	#mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	mgmt = d1['mgmt']['intf']
	#mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + vrr_file +",device=disk,bus=ide,format=qcow2 "
	#cmd_head +="--ram 1024 --vcpu 1 --os-type linux --os-variant rhel7  --arch=x86_64 "
	#cmd_head +="--ram 1024 --vcpu 1 "
	cmd_head +="--memory=1024,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	if 'mac' in d1['nodes'][node]['mgmt'].keys():
		cmd_head +="--network bridge=" + mgmt+",model=virtio,mac=" + d1['nodes'][node]['mgmt']['mac'] + " " 
	else:
		cmd_head +="--network bridge=" + mgmt+",model=virtio " 
	cmd_tail="--console pty,target_type=serial --noautoconsole --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml

def create_cvx_xml(node, d1):
	lab_name = d1['lab_name']
	cvx_file = d1['files']['cvx']['re_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	#mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	mgmt = d1['mgmt']['intf']
	#mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + cvx_file +",device=disk "
	# cmd_head +="--ram 1024 --vcpu 1 --os-type linux --os-variant rhel7  --arch=x86_64 "
	#cmd_head +="--ram 1024 --vcpu 1 "
	cmd_head +="--memory=1024,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	if 'mac' in d1['nodes'][node]['mgmt'].keys():
		cmd_head +="--network bridge=" + mgmt+",model=virtio,mac=" + d1['nodes'][node]['mgmt']['mac'] + " " 
	else:
		cmd_head +="--network bridge=" + mgmt+",model=virtio " 
	cmd_tail="--console pty,target_type=serial --noautoconsole --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml

