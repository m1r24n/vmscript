#!/usr/bin/env python3
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
DUMMY_BRIDGE='dumbr0'

def virtinstall2xml(virtinstallCMD,mgmt):
	# root=tree.getroot()
	result1=os.popen(virtinstallCMD).read()
	#print(result1)
	root=ET.fromstring(result1)
	# removing UUID from xml 
	for i in root.findall('uuid'):
		#print(i,i.tag)
		root.remove(i)
	dev=root.find('devices')
	#print(dev,dev.tag)
	for intf in dev.findall('interface'):
		mac=intf.find('mac')
		# removing MAC address tag from XML
		intf.remove(mac)
		# add mtu into XML
		mtu=ET.Element('mtu',{'size':MTU})
		#print(ET.tostring(mtu))
		intf.insert(0,mtu)
		#print(mac,mac.tag)
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
		list_of_intf = ['ge-0/0/0','ge-0/0/1','ge-0/0/2','ge-0/0/3','ge-0/0/4','ge-0/0/5','ge-0/0/6','ge-0/0/7','ge-0/0/8',
					    'ge-0/0/9']
	elif d1['nodes'][node]['type'] == 'vqfx':
		list_of_intf = ['xe-0/0/0','xe-0/0/1','xe-0/0/2','xe-0/0/3','xe-0/0/4','xe-0/0/5','xe-0/0/6','xe-0/0/7','xe-0/0/8',
					    'xe-0/0/9','xe-0/0/10','xe-0/0/11']
	elif d1['nodes'][node]['type'] == 'vsrx':
		list_of_intf = ['ge-0/0/0','ge-0/0/1','ge-0/0/2','ge-0/0/3','ge-0/0/4','ge-0/0/5','ge-0/0/6','ge-0/0/7']
	for i in list_of_intf:
		ovs=False
		target_name = lab_name + "_" + node + "_" + i.split('-')[0] + "_" + i.split('-')[1].split('/')[2]
		if i in interfaces:
			if 'bridge' in d1['nodes'][node]['interfaces'][i]:
				bridge_name = d1['nodes'][node]['interfaces'][i]['bridge']
				if 'brtype' in d1['nodes'][node]['interfaces'][i]:
					if d1['nodes'][node]['interfaces'][i]['brtype']=='ovs':
						ovs=True
				if ovs:
					cmd_list += "--network bridge=" + bridge_name + ",model=" + model + ",target=" + target_name + ",virtualport_type=openvswitch "
				else:
					cmd_list += "--network bridge=" + bridge_name + ",model=" + model + ",target=" + target_name + " "
		else:
			cmd_list += "--network bridge=" + DUMMY_BRIDGE + ",model=" + model + ",target=" + target_name + " "

	return cmd_list

def mgmt_bridge(d1):
	retval = d1['mgmt']['intf']
	return retval

def is_hugepages(d1):
	retval = False
	if 'hugepages' in d1.keys():
		retval = d1['hugepages']
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
	if is_hugepages(d1):
		cmd_head +="--memory=2048,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	else:
		cmd_head +="--memory=2048 --vcpu 1 "
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
	if is_hugepages(d1):
		cmd_head +="--memory=2048,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	else:
		cmd_head +="--memory=2048 --vcpu 1 "
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
	if is_hugepages(d1):
		cmd_head +="--memory=4096,hugepages=yes --memorybacking hugepages=yes --vcpu 2 "
	else:
		cmd_head +="--memory=4096 --vcpu 2 "
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
	if is_hugepages(d1):
		cmd_head +="--memory=4096,hugepages=yes --memorybacking hugepages=yes --vcpu 4 "
	else:
		cmd_head +="--memory=4096 --vcpu 4 "
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
	if is_hugepages(d1):
		cmd_head +="--memory=1024,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	else:
		cmd_head +="--memory=1024 --vcpu 1 "
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
	if is_hugepages(d1):
		#cmd_head +="--memory=3072,hugepages=yes --memorybacking hugepages=yes --vcpu 3 "
		cmd_head +="--memory=2048,hugepages=yes --memorybacking hugepages=yes --vcpu 3 "
	else:
		#cmd_head +="--memory=3072 --vcpu 3 "
		cmd_head +="--memory=2048 --vcpu 3 "
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
	if is_hugepages(d1):
		cmd_head +="--memory=1024,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	else:
		cmd_head +="--memory=1024 --vcpu 1 "
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
	if is_hugepages(d1):
		cmd_head +="--memory=1024,hugepages=yes --memorybacking hugepages=yes --vcpu 1 "
	else:
		cmd_head +="--memory=1024 --vcpu 1 "
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

