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
		if 'bridge' in d1['nodes'][node]['interfaces'][i]:
			if d1['nodes'][node]['interfaces'][i]['bridge'] in exist_bridge:
				bridge_name = d1['nodes'][node]['interfaces'][i]['bridge']
			else:
				bridge_name = lab_name + "-" + d1['nodes'][node]['interfaces'][i]['bridge']
			cmd_list += "--network bridge=" + bridge_name + ",model=" + model + " " 

	return cmd_list

def mgmt_bridge(d1):
	if 'exist_bridge' in d1.keys():
		eb=d1['exist_bridge']
	else:
		eb=['']
	
	if d1['mgmt']['intf'] in eb:
		retval = d1['mgmt']['intf']
	else:
		retval = d1['lab_name'] + "-" + d1['mgmt']['intf']
	return retval


def create_vpfe_vqfx_xml(node,d1): 
	lab_name = d1['lab_name']
	pfe_file = d1['files']['vqfx']['pfe_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vpfe-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + pfe_file +",device=disk,bus=ide "
	cmd_head +="--ram 1536 --vcpu 1 --os-type linux --os-variant generic "
	cmd_head +="--network bridge=" + mgmt+",model=e1000 "
	cmd_head +="--network bridge=" + lab_name +"Int" + node + ",model=e1000 " 
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
	mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vcp-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + re_file +",device=disk,bus=ide "
	cmd_head +="--ram 2048 --vcpu 1 --os-type linux --os-variant generic "
	# cmd_head +="--ram 1024 --vcpu 1 --os-type linux --os-variant generic "
	cmd_head +="--network bridge=" + mgmt+",model=e1000,mac=" + d1['nodes'][node]['fxp0']['mac'] + " " 
	cmd_head +="--network bridge=" + lab_name +"Int" + node + ",model=e1000 " 
	cmd_head +="--network bridge=" + lab_name +"Int" + node +",model=e1000 " 
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
	mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + vsrx_file +",device=disk,bus=ide,size=16,format=qcow2 "
	cmd_head +="--ram 4096 --vcpu 2 --os-type linux --os-variant rhel7  --arch=x86_64 "
	cmd_head +="--cpu SandyBridge,+pbe,+tm2,+est,+vmx,+osxsave,+smx,+ss,+ds,+vme,+dtes64,+monitor,+ht,+dca,+pcid,+tm,+pdcm,+pdpe1gb,+ds_cpl,+xtpr,+acpi,-invtsc "
	cmd_head +="--network bridge=" + mgmt+",model=e1000,mac=" + d1['nodes'][node]['fxp0']['mac'] + " "
	cmd_tail="--console pty,target_type=serial --noautoconsole --hvm --accelerate --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml

def create_vcp_vmx_xml(node, d1):
	lab_name = d1['lab_name']
	re_file = d1['files']['vmx']['re_file']
	interfaces = list(d1['nodes'][node]['interfaces'])
	interfaces.sort()
	dest_dir=d1['image_destination']
	# mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vcp-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + re_file +",device=disk,bus=ide,format=qcow2 "
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/vmxhdd.img,device=disk,bus=ide,format=qcow2 "
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/metadata-usb-re.img,device=disk,bus=ide,format=raw "
	cmd_head +="--ram 1024 --vcpu 1 --os-type linux --os-variant rhel7  --arch=x86_64 "
	cmd_head +="--network bridge=" + mgmt+",model=virtio,mac=" + d1['nodes'][node]['fxp0']['mac'] + " "
	cmd_head +="--network bridge=" + lab_name + "Int" + node+",model=virtio "
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
	mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-vpfe-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + pfe_file +",device=disk,bus=ide,format=qcow2 "
	cmd_head +="--ram 3072 --vcpu 4 --os-type linux --os-variant rhel7  --arch=x86_64 "
	cmd_head +="--cpu host-passthrough "
	cmd_head +="--network bridge=" + mgmt+",model=virtio "
	cmd_head +="--network bridge=" + lab_name+"Int" + node +",model=virtio "
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
	mgmt = mgmt_bridge(d1)
	cmd_head="virt-install --name " + lab_name + "-" + node 
	cmd_head += " --disk " + dest_dir + "/" + lab_name + "/" + node + "/" + vrr_file +",device=disk,bus=ide,format=qcow2 "
	cmd_head +="--ram 1024 --vcpu 4 --os-type linux --os-variant rhel7  --arch=x86_64 "
	cmd_head +="--network bridge=" + mgmt+",model=virtio,mac=" + d1['nodes'][node]['fxp0']['mac'] + " "
	cmd_tail="--console pty,target_type=serial --noautoconsole --graphics vnc,password=" +VNC_PASSWORD +",listen=0.0.0.0 --virt-type=kvm --boot hd --print-xml "
	cmd1 = cmd_head + intfcmd(node,d1) + cmd_tail
	# print("command ", cmd1)
	xml=virtinstall2xml(cmd1,mgmt)
	# print(xml)
	return xml
