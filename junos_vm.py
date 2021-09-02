#!/usr/bin/env python3
import sys
import os
import pynetlinux
import subprocess
import libvirt
import yaml
import traceback
import shutil 
import junos_vm_xml
from jinja2 import Template
import pexpect
import jnpr.junos
from jnpr.junos import Device
from jnpr.junos.utils.config import Config
from jnpr.junos.utils.scp import SCP
# from jnpr.junos.utils.sw import SW
from ovs_vsctl import VSCtl
import json

# install ovs_vsctl : sudo pip3 install git+https://github.com/iwaseyusuke/python-ovs-vsctl.git
# from jnpr.junos import Device
# from jnpr.junos.utils.config import Config
from passlib.hash import md5_crypt

#  change GROUP_FWD_MASK to 0x4000 if standard bridge kernel module is used
# 0x4000 is to allow only LLDP
# 0x400c is to allow only LLDP and LACP
# LACP Requires modified bridge kernel module
MTU = 9000
GROUP_FWD_MASK="0x400c"
DUMMY_BRIDGE='dumbr0'
#GROUP_FWD_MASK="0x4000"
SLAX_SCRIPT='/home/debian/git/vmscript/scripts/rpm-log.slax'
mask_ipv4 = 0b1
mask_ipv6 = 0b10
mask_iso  = 0b100
mask_mpls = 0b1000
mask_isis = 0b10000
mask_rsvp = 0b100000
mask_ldp  = 0b1000000

def print_syntax():
	print("usage : vmm.py <-c filename> <command> <vm_name>")
	print("commands are : ")
	print("  addbr : to add bridge (requires sudo)")
	print("  delbr : to del bridge (requires sudo)")
	print("  definevm : to add VM into KVM hypervisor")
	print("  undefinevm : to remove VM from KVM hypervisor")
	print("  start : to start junos VM (it must be followed by VM name or all to start ) ")
	print("  stop : to stop junos VM (it must be followed by VM name or all to stop )")
	print("  init_vm : to set management IP and password of Junos VM ")
	print("  config : to config junos VM ")
	print("  config4ns : add configuration for Northstar ")

def check_argv(argv):
	retval={}
	len_argv=len(argv)
	cmd_list=['addbr','delbr','definevm','undefinevm','stop','start','config','init_vm','config4ns']
	#print("len ",len_argv)
	if len_argv > 3:
		if '-c' in argv:
			index_c = argv.index("-c")
			if (len_argv - 1) > index_c:
				if not os.path.isfile(argv[index_c + 1]):
					print("file %s doesn't exist, please create one or define another file for configuration" % (argv[index_c + 1]))
				else:
					t1 = argv[0].split("/")
					path=""
					for i in list(range(2)):
						path += t1[i] + "/"
					#print("path ",path)
					
					retval['config_file']=argv[index_c + 1]
					argv.pop(index_c + 1)
					argv.pop(index_c)
					argv.pop(0)
					len_1 = len(argv)
					len_2 = len(set(argv))
					if len_1 >  len_2:
						print("syntax error, there is duplicated argument")
					else:
						#print("argv ",argv)
						
						if argv[0] not in cmd_list:
							print("%s is not the correct command" %(argv[0]))
						else:
							#print("reach here ",len(argv))
							if len(argv)==1:
								retval['cmd']=argv[0]
								retval['nodes']='all'
							else:
								retval['cmd']=argv[0]
								retval['nodes']=argv[1]
							retval['path']=path
	# print("Retval ",retval)
	return retval

def read_config(config1):
	print("configuration file ",config1['config_file'])
	d1={}
	try:
		f1=open(config1['config_file'])
		d1=yaml.load(f1,Loader=yaml.FullLoader)
		f1.close()
		d1['config']=config1
		if 'fabric' in d1.keys():
			num_link = len(d1['fabric']['topology'])
			pref_len = 32 - int(d1['fabric']['subnet'].split('/')[1])
			num_subnet = int( (2 **  pref_len) / 2)		
			if num_link > num_subnet:
				print("not enough ip address for fabric link\nnum of link %d, num of subnet %d " %(num_link,num_subnet))
				d1={}
			elif check_ip(d1):
				print("wrong subnet allocation")
				print("subnet %s can't be used with prefix %s" %(d1['fabric']['subnet'].split('/')[0],d1['fabric']['subnet'].split('/')[1]))
			elif not check_vm(d1):
				print("number of VM on topology doesn't match with on configuration")
			else:
				create_config_interfaces(d1)

	except FileNotFoundError:
		print("where is the file")
	except PermissionError:
		print("Permission error")

	return d1

def create_config_interfaces(d1):
	num_link = len(d1['fabric']['topology'])
	b1,b2,b3,b4 = d1['fabric']['subnet'].split('/')[0].split('.')
	start_ip = (int(b1) << 24) + (int(b2) << 16) + (int(b3) << 8) + int(b4)
	for i in range(num_link):
		# br=d1['lab_name'] + '_ptp' + str(i)
		br= 'ptp' + str(i)
		d1['fabric']['topology'][i].append(br)
		if d1['fabric']['topology'][i][0]:
			if d1['fabric']['topology'][i][0] & mask_ipv4:
				d1['fabric']['topology'][i].append(bin2ip(start_ip))
				start_ip += 1
				d1['fabric']['topology'][i].append(bin2ip(start_ip))
				start_ip += 1
			else:
				d1['fabric']['topology'][i].append('0')
				d1['fabric']['topology'][i].append('0')
	list_vm = list_vm_from_fabric(d1)
	d2={'nodes': {} }
	for i in list_vm:
		d2['nodes'].update({i : {'interfaces': {}}})
		for j in d1['fabric']['topology']:
			if j[1] == i:
				d2['nodes'][i]['interfaces'].update( {j[2]: {'bridge' : j[5]} })
				if j[0] & mask_ipv4:
					if 'family' not in d2['nodes'][i]['interfaces'][j[2]].keys():
						d2['nodes'][i]['interfaces'][j[2]].update({'family' : {'inet': j[6]}})
					else:
						d2['nodes'][i]['interfaces'][j[2]]['family'].update({'inet': j[6]})
					if j[0] & mask_iso:
						if 'family' not in d2['nodes'][i]['interfaces'][j[2]].keys():
							d2['nodes'][i]['interfaces'][j[2]].update({'family' : {'iso':None}})
						else:
							d2['nodes'][i]['interfaces'][j[2]]['family'].update({'iso':None})
						if j[0] & mask_isis:
							if 'protocol' not in d2['nodes'][i]['interfaces'][j[2]].keys():
								d2['nodes'][i]['interfaces'][j[2]].update({'protocol' : {'isis':'ptp'}})
							else:
								d2['nodes'][i]['interfaces'][j[2]]['protocol'].update({'isis':'ptp'})
					if j[0] & mask_mpls:
						if 'family' not in d2['nodes'][i]['interfaces'][j[2]].keys():
							d2['nodes'][i]['interfaces'][j[2]].update({'family' : {'mpls':None}})
						else:
							d2['nodes'][i]['interfaces'][j[2]]['family'].update({'mpls':None})
						if j[0] & mask_rsvp:
							if 'protocol' not in d2['nodes'][i]['interfaces'][j[2]].keys():
								d2['nodes'][i]['interfaces'][j[2]].update({'protocol' : {'rsvp':None}})
							else:
								d2['nodes'][i]['interfaces'][j[2]]['protocol'].update({'rsvp':None})
						if j[0] & mask_ldp:
							if 'protocol' not in d2['nodes'][i]['interfaces'][j[2]].keys():
								d2['nodes'][i]['interfaces'][j[2]].update({'protocol' : {'ldp':None}})
							else:
								d2['nodes'][i]['interfaces'][j[2]]['protocol'].update({'ldp':None})

			elif j[3] == i:
				d2['nodes'][i]['interfaces'].update({j[4]: {'bridge' : j[5]} })
				if j[0] & mask_ipv4:
					if 'family' not in d2['nodes'][i]['interfaces'][j[4]].keys():
						d2['nodes'][i]['interfaces'][j[4]].update({'family' : {'inet': j[7]}})
					else:
						d2['nodes'][i]['interfaces'][j[4]]['family'].update({'inet': j[7]})
					
					if j[0] & mask_iso:
						if 'family' not in d2['nodes'][i]['interfaces'][j[4]].keys():
							d2['nodes'][i]['interfaces'][j[4]].update({'family' : {'iso':None}})
						else:
							d2['nodes'][i]['interfaces'][j[4]]['family'].update({'iso':None})
						if j[0] & mask_isis:
							if 'protocol' not in d2['nodes'][i]['interfaces'][j[4]].keys():
								d2['nodes'][i]['interfaces'][j[4]].update({'protocol' : {'isis':'ptp'}})
							else:
								d2['nodes'][i]['interfaces'][j[4]]['protocol'].update({'isis':'ptp'})

					if j[0] & mask_mpls:
						if 'family' not in d2['nodes'][i]['interfaces'][j[4]].keys():
							d2['nodes'][i]['interfaces'][j[4]].update({'family' : {'mpls':None}})
						else:
							d2['nodes'][i]['interfaces'][j[4]]['family'].update({'mpls':None})
					
						if j[0] & mask_rsvp:
							if 'protocol' not in d2['nodes'][i]['interfaces'][j[4]].keys():
								d2['nodes'][i]['interfaces'][j[4]].update({'protocol' : {'rsvp':None}})
							else:
								d2['nodes'][i]['interfaces'][j[4]]['protocol'].update({'rsvp':None})
						if j[0] & mask_ldp:
							if 'protocol' not in d2['nodes'][i]['interfaces'][j[4]].keys():
								d2['nodes'][i]['interfaces'][j[4]].update({'protocol' : {'ldp':None}})
							else:
								d2['nodes'][i]['interfaces'][j[4]]['protocol'].update({'ldp':None})

	for i in d2['nodes'].keys():
		intf = d2['nodes'][i]['interfaces']
		if not d1['nodes'][i]['interfaces']:
			# print("null interface, host ",i)
			d1['nodes'][i]['interfaces']=intf
		else:
			d1['nodes'][i]['interfaces'].update(intf)				
	#print(json.dumps(d1,sort_keys=False, indent=4))
	#pprint.pprint(d2)

def list_vm_from_fabric(d1):
	retval = []
	for i in d1['fabric']['topology']:
		if i[1] not in retval:
			retval.append(i[1])
		if i[3] not in retval:
			retval.append(i[3])
	return retval

def bin2ip(ipbin):
	m1 = 255<<24
	m2 = 255<<16
	m3 = 255 << 8
	m4 = 255
	b1=str((ipbin & m1) >> 24)
	b2=str((ipbin & m2) >> 16)
	b3=str((ipbin & m3) >> 8)
	b4=str(ipbin & m4)
	retval = '.'.join((b1,b2,b3,b4)) + "/31"
	#print(retval)
	return retval


def check_ip(d1):
	preflen = 32 - int(d1['fabric']['subnet'].split('/')[1])
	mask_ip = int(2** preflen - 1) 
	b1,b2,b3,b4 = d1['fabric']['subnet'].split('/')[0].split('.')
	ip_int = (int(b1) << 24) + (int(b2) << 16) + (int(b3) << 8) + int(b4)
	#print("ip int : ",bin(ip_int))
	#print("mask   : ",bin(mask_ip))
	retval = ip_int & mask_ip
	#print("retval = ",retval)
	return retval

def check_vm(d1):
	vm_d1 = []
	vm_d1 = d1['nodes'].keys()
	vm_f1= list_vm_from_fabric(d1)
	return set(vm_f1).issubset(set(vm_d1))

def check_existing_bridge(d1):
	if 'exist_bridge' in d1.keys():
		eb=d1['exist_bridge']
	else:
		eb=['']
	return eb

def do_bridge(d1):
	cmd1=d1['config']['cmd']
	#mgmt_intf=d1['lab_name']+ "-" +d1['mgmt']['intf']
	mgmt_intf=d1['mgmt']['intf']
	(mgmt_ip,mgmt_netmask)=d1['mgmt']['ip'].split("/")
	print("management ip ", mgmt_ip)
	print("management netmask ", mgmt_netmask)
	lab_name=d1['lab_name']
	nodes=list(d1['nodes'].keys())
	eb = check_existing_bridge(d1)
	ovs_bridges=[]
	if d1['mgmt']['intf'] not in eb:
		bridges=[mgmt_intf]
	else:
		bridges=[]
	bridges.append(DUMMY_BRIDGE)
	for i in nodes:
		'''
		# original code
		for j in list(d1['nodes'][i]['interfaces'].values()):
		if j not in bridges:
				if j not in eb:
					bridges.append(lab_name + "-" + j)
		'''
		for j in list(d1['nodes'][i]['interfaces'].keys()):	
			if 'bridge' in d1['nodes'][i]['interfaces'][j].keys() and 'brtype' not in d1['nodes'][i]['interfaces'][j].keys():
				if d1['nodes'][i]['interfaces'][j]['bridge'] not in eb:
					if d1['nodes'][i]['interfaces'][j]['bridge'] not in bridges:
						# bridges.append(lab_name + "-" + d1['nodes'][i]['interfaces'][j]['bridge'])
						bridges.append(d1['nodes'][i]['interfaces'][j]['bridge'])
			if 'bridge' in d1['nodes'][i]['interfaces'][j].keys() and 'brtype' in d1['nodes'][i]['interfaces'][j].keys():
				if d1['nodes'][i]['interfaces'][j]['brtype'] == 'lb':
					if d1['nodes'][i]['interfaces'][j]['bridge'] not in bridges:
						bridges.append(d1['nodes'][i]['interfaces'][j]['bridge'])
				elif d1['nodes'][i]['interfaces'][j]['brtype'] == 'ovs':
					if d1['nodes'][i]['interfaces'][j]['bridge'] not in ovs_bridges:
						ovs_bridges.append(d1['nodes'][i]['interfaces'][j]['bridge'])
	for i in nodes:
		if d1['nodes'][i]['type'] not in ['vsrx','cvx','vrr','vmx-n']:
			# bridges.append(lab_name + "Int" + i)
			bridges.append("Int" + i)
	#b1 = set(bridges) - set(eb)
	#bridges=list(b1)
	for i in bridges:
		if cmd1=='addbr':
			if not pynetlinux.brctl.findbridge(i.encode('UTF-8')):
				print("Creating bridge ",i)
				pynetlinux.brctl.addbr(i)	
				# intf=pynetlinux.ifconfig.findif(i.encode('UTF-8'),physical=False)
				intf=pynetlinux.ifconfig.Interface(i.encode('UTF-8'))
				intf.up()
				# set /sys/class/net/topo5-Vqfx2lan3/bridge/group_fwd_mask
				path1="/sys/class/net/" + i + "/bridge/group_fwd_mask"
				path2="/sys/devices/virtual/net/" + i + "/bridge/multicast_snooping"
				path3="/proc/sys/net/ipv6/conf/" + i + "/disable_ipv6"
				arg=[]
				arg.append("echo " + GROUP_FWD_MASK + " > " +  path1) 
				arg.append("echo 0 > " + path2) 
				arg.append("echo 1 > " + path3) 
				for i in arg:
					# print(i)
					cmd=["bash", "-c",i]
					result=subprocess.Popen(cmd)
			else:
				print("Bridge ",i," already exist")
		elif cmd1=='delbr':
			br1=pynetlinux.brctl.findbridge(i.encode('UTF-8'))
			if br1:
			# if pynetlinux.brctl.findbridge(i.encode('UTF-8')):
				print("Deleting bridge ",i)
			#	intf=pynetlinux.ifconfig.Interface(i.encode('UTF-8'))
			#	intf.down()
			#	pynetlinux.brctl.delbr(i)	
				br1.delete()
			else:
				print("Bridge ",i," does not exist")
	if cmd1=='addbr' and d1['mgmt']['intf'] not in eb:
		intf=pynetlinux.ifconfig.Interface(mgmt_intf.encode('UTF-8'))
		intf.set_ip(mgmt_ip)
		intf.set_netmask(int(mgmt_netmask))
	if ovs_bridges:
		if cmd1=='addbr':
			print('creating ovs',ovs_bridges)
			vsctl = VSCtl('tcp', '127.0.0.1', 6640)
			for i in ovs_bridges:
				cmd1 = "add-br " + i
				popen=vsctl.run(command=cmd1)
		elif cmd1=='delbr':
			print('deleting ovs',ovs_bridges)
			vsctl = VSCtl('tcp', '127.0.0.1', 6640)
			for i in ovs_bridges:
				cmd1 = "del-br " + i
				popen=vsctl.run(command=cmd1)

def send_init(i):
	my_hash_root = md5_crypt.hash(i['root_password'])
	my_hash = md5_crypt.hash(i['password'])
	c1="virsh console " + i['nodes']
	print("configuring ",i['nodes'])
	if i['type'] == 'vqfx':
		'''s_e = [
				["","login:"],
				["root", "root@:RE:0%"],
				["cli","root>"],
				["edit","root#"],
				["delete interfaces","root#"],
				["set system host-name " + i['hostname'],"root#"],
				["set system root-authentication encrypted-password \"" + my_hash_root + "\"","root#"],
				["set system services ssh","root#"],
				["set system services netconf ssh","root#"],
				["set system login user " +  i['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"","root#"],
				["set interfaces em0.0 family inet address " + i['mgmt'],"root#"],
				["set interfaces em1.0 family inet address 169.254.0.2/24","root#"],
				["set system management-instance","root#"],
				["set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + i['gateway4'], "root#"],
				["commit","root@"],
				["exit","root@"],
				["exit","root@"],
				["exit","login:"]
		'''
		s_e = [
				["","login:"],
				["root", "root@:RE:0%"],
				["cli","root>"],
				["edit","root#"],
				["set system host-name " + i['hostname'],"root#"],
				["set system root-authentication encrypted-password \"" + my_hash_root + "\"","root#"],
				["set system services ssh","root#"],
				["set system services netconf ssh","root#"],
				["set system login user " +  i['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"","root#"],
				["set interfaces em0.0 family inet address " + i['mgmt'],"root#"],
				["set system management-instance","root#"],
				["set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + i['gateway4'], "root#"],
				["commit","root@"],
				["exit","root@"],
				["exit","root@"],
				["exit","login:"]
			]
	elif i['type'] == 'vmx-n':
		s_e = [
			["","login:"],
			["root","root@"],
			["cli","root>"],
			["edit","root#"],
			["delete interfaces fxp0","root#"],
			["delete chassis","root#"],
			["delete protocols","root#"],
			["delete system processes dhcp-service","root#"],
			["set system host-name " + i['hostname'],"root#"],
			["set system root-authentication encrypted-password \"" + my_hash_root + "\"","root#"],
			["set system services ssh","root#"],
			["set system services netconf ssh","root#"],
			["set system login user " +  i['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"","root#"],
			["set interfaces fxp0.0 family inet address " + i['mgmt'],"root#"],
			["set system management-instance","root#"],
			["set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + i['gateway4'], "root#"],
			["set chassis fpc 0 lite-mode","root#"],
			["set chassis network-services enhanced-ip","root#"],
			["set snmp community public authorization read-only","root#"],
			["commit","root@"+i['hostname']+"#"],
			["exit","root@"+i['hostname']+">"],
			["exit","root@:~ #"],
			["exit","login:"]
		] 
	elif i['type'] == 'vmx':
		if i['dual_re']:
			s_e = [
					["","login:"],
					["root","root@"],
					["cli","root>"],
					["edit","root#"],
					["delete interfaces fxp0","root#"],
					["delete chassis","root#"],
					["delete protocols","root#"],
					["delete system processes dhcp-service","root#"],
					["set system host-name " + i['hostname'],"root#"],
					["set system root-authentication encrypted-password \"" + my_hash_root + "\"","root#"],
					["set system services ssh","root#"],
					["set system services netconf ssh","root#"],
					["set system login user " +  i['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"","root#"],
					["set groups re0 interfaces fxp0.0 family inet address " + i['mgmt_re0'],"root#"],
					["set groups re1 interfaces fxp0.0 family inet address " + i['mgmt_re1'],"root#"],
					["set apply-groups re0","root#"],
					["set apply-groups re1","root#"],
					["set system management-instance","root#"],
					["set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + i['gateway4'], "root#"],
					["set chassis fpc 0 lite-mode","root#"],
					["set chassis redundancy routing-engine 0 master","root#"],
					["set chassis redundancy routing-engine 1 backup","root#"],
					["set chassis redundancy graceful-switchover","root#"],
					["set chassis network-services enhanced-ip","root#"],
					["set system commit synchronize","root#"],
					["set snmp community public authorization read-only","root#"],
					["commit synchronize","root@"+i['hostname']+"#"],
					["exit","root@"+i['hostname']+">"],
					["exit","root@:~ #"],
					["exit","login:"]
			] 
		else:
			s_e = [
					["","login:"],
					["root","root@"],
					["cli","root>"],
					["edit","root#"],
					["delete interfaces fxp0","root#"],
					["delete chassis","root#"],
					["delete protocols","root#"],
					["delete system processes dhcp-service","root#"],
					["set system host-name " + i['hostname'],"root#"],
					["set system root-authentication encrypted-password \"" + my_hash_root + "\"","root#"],
					["set system services ssh","root#"],
					["set system services netconf ssh","root#"],
					["set system login user " +  i['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"","root#"],
					["set interfaces fxp0.0 family inet address " + i['mgmt'],"root#"],
					["set system management-instance","root#"],
					["set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + i['gateway4'], "root#"],
					["set chassis fpc 0 lite-mode","root#"],
					["set chassis network-services enhanced-ip","root#"],
					["set snmp community public authorization read-only","root#"],
					["commit","root@"+i['hostname']+"#"],
					["exit","root@"+i['hostname']+">"],
					["exit","root@:~ #"],
					["exit","login:"]
			] 
	elif i['type'] == 'vsrx':
		s_e = [
				["","login:"],
				["root","root@"],
				["cli","root>"],
				["edit","root#"],
				["set system host-name " + i['hostname'],"root#"],
				["set system root-authentication encrypted-password \"" + my_hash_root + "\"","root#"],
				["set system services ssh","root#"],
				["set system services netconf ssh","root#"],
				["set system login user " +  i['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"","root#"],
				["set interfaces fxp0.0 family inet address " + i['mgmt'],"root#"],
				["set system management-instance","root#"],
				["set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + i['gateway4'], "root#"],
				["set snmp community public authorization read-only","root#"],
				["commit","root@"+i['hostname']+"#"],
				["exit","root@"+i['hostname']+">"],
				["exit","root@:~ #"],
				["exit","login:"]
			] 
	# print(s_e)
	p1=pexpect.spawn(c1)
	for j in s_e:
		print("send :",j[0])
		p1.sendline(j[0])
		print("expect : ",j[1])
		p1.expect(j[1])
	p1.close()

def init_vm(d1):
	vm = d1['config']['nodes']
	if vm == 'all':
		for i in d1['nodes'].keys():
			d2 = create_data(d1,i)
			send_init(d2)
	elif vm not in d1['nodes'].keys():
		print("VM %s is not defined in the configuration " %(vm))
	else:
		print("init config for VM %s" %(vm))
		d2 = create_data(d1,vm)
		send_init(d2)
			
def create_data(d1,i):
	retval = {}
	if dual_re(d1,i):
		retval= {
			'password':d1['login']['password'],
			'root_password':d1['login']['root_password'],
			'user':d1['login']['user'],
			'nodes' : d1['lab_name'] +"-vcp0-" +  i,
			'hostname' : i,
			'dual_re' : True,
			'mgmt_re0' : d1['nodes'][i]['mgmt']['ip'][0],
			'mgmt_re1' : d1['nodes'][i]['mgmt']['ip'][1],
			'gateway4' : d1['mgmt']['ip'].split('/')[0],
			'type' :d1['nodes'][i]['type']
		}
	else:
		if d1['nodes'][i]['type']=='vmx-n':
			retval= {
				'password':d1['login']['password'],
				'root_password':d1['login']['root_password'],
				'user':d1['login']['user'],
				'nodes' : d1['lab_name'] +"-vmx-" +  i,
				'hostname' : i,
				'dual_re' : False,
				'mgmt' : d1['nodes'][i]['mgmt']['ip'][0],
				'gateway4' : d1['mgmt']['ip'].split('/')[0],
				'type' :d1['nodes'][i]['type']
			}
		else:
			if d1['nodes'][i]['type'] == 'vsrx':
				retval= {
					'password':d1['login']['password'],
					'root_password':d1['login']['root_password'],
					'user':d1['login']['user'],
					'nodes' : d1['lab_name'] + "-" +  i,
					'hostname' : i,
					'dual_re' : False,
					'mgmt' : d1['nodes'][i]['mgmt']['ip'][0],
					'gateway4' : d1['mgmt']['ip'].split('/')[0],
					'type' :d1['nodes'][i]['type']
				}
			else:
				retval= {
					'password':d1['login']['password'],
					'root_password':d1['login']['root_password'],
					'user':d1['login']['user'],
					'nodes' : d1['lab_name'] +"-vcp-" +  i,
					'hostname' : i,
					'dual_re' : False,
					'mgmt' : d1['nodes'][i]['mgmt']['ip'][0],
					'gateway4' : d1['mgmt']['ip'].split('/')[0],
					'type' :d1['nodes'][i]['type']
				}
	return retval

def config_junos(d1):
	vm = d1['config']['nodes']
	if vm == 'all':
		for i in d1['nodes'].keys():
			create_junos_config(d1,i)
	elif vm not in d1['nodes'].keys():
		print("VM %s is not defined in the configuration" % (vm))
	else:
		create_junos_config(d1,vm)

def config4ns(d1):
	vm = d1['config']['nodes']
	#print("not yet implemented")
	#print("VM ",vm)
	if vm == 'all':
		for i in d1['nodes'].keys():
			config4nsdeploy(d1,i)
	elif vm not in d1['nodes'].keys():
		print("VM %s is not defined in the configuration" % (vm))
	else:
		config4nsdeploy(d1,vm)

def config4nsdeploy(d1,vm):
	status=0
	f1=open(d1['config']['path']+"rpm_ns.j2") 
	jt=f1.read()
	f1.close()
	template_config=Template(jt)
	# set interfaces {{ intf }}.0 local {{ interfaces[intf].source }} target {{ interfaces[intf].target }}
	print("deploying configuration required for Northstar")
	if d1['nodes'][vm]['type'] != 'vmx':
		print("not implemented yet for ",d1['nodes'][i]['type'])
	else:
		data1={}
		if 'ns' in d1.keys():
			if 'ip' in d1['ns'].keys() and 'port' in d1['ns'].keys():
				data1['ns_ip']=d1['ns']['ip']
				data1['ns_port']=d1['ns']['port']
				status = status | 1
		if 'lo0' in d1['nodes'][vm]['interfaces'].keys():
			if 'family' in d1['nodes'][vm]['interfaces']['lo0'].keys():
				if 'inet' in d1['nodes'][vm]['interfaces']['lo0']['family']:
					data1['local_address'] = d1['nodes'][vm]['interfaces']['lo0']['family']['inet'].split('/')[0]
					status = status | 2
		data1['interfaces']={}
		for i in d1['nodes'][vm]['interfaces'].keys():
			if 'family' in d1['nodes'][vm]['interfaces'][i].keys():
				if 'mpls' in d1['nodes'][vm]['interfaces'][i]['family'] and 'inet' in d1['nodes'][vm]['interfaces'][i]['family']:
					data1['interfaces'][i]={} 
					src_ip = d1['nodes'][vm]['interfaces'][i]['family']['inet'].split('/')[0]
					dst_ip = calc_target(src_ip)
					data1['interfaces'][i]['source']=src_ip
					data1['interfaces'][i]['target']=dst_ip
					
		if status == 3:
			# print(data1)
			config1 = template_config.render(data1)
			print("uploading configuration into %s" %(vm))
			#print(config1)
			ip = d1['nodes'][vm]['mgmt']['ip'].split('/')[0]
			#ip = data1['local_address']
			user=d1['login']['user']
			passwd = d1['login']['password']
			#print("ip %s, user %s, password %s" %(ip,user,passwd))
			try:
				dev=Device(host=ip,user=user,password=passwd,gather_facts=False).open()
				#print(dev.facts)
				with SCP(dev) as scp:
					scp.put(SLAX_SCRIPT,remote_path='/var/db/scripts/event')
				with Config(dev) as cu:  
					cu.load(config1,format='set')
					cu.commit()
				# sw=SW(dev)
				# sw.reboot()
				dev.close()
			except jnpr.junos.exception.ConnectRefusedError:
				print("connection error")
		else:
			if (status & 1 ==0):
				print("NS ip address is no configured")
			if (status & 2 ==0):
				print(("loopback address is not configured"))

def calc_target(src_ip):
	ip_byte = src_ip.split('.')
	if int(ip_byte[3]) % 2:
		ip_byte[3]=str(int(ip_byte[3])-1)
	else:
		ip_byte[3]=str(int(ip_byte[3])+1)
	return '.'.join(ip_byte)


def create_junos_config(d1,i):
	print("Create junos configuration for node %s" %(i))
	f1=open(d1['config']['path'] + "junos.j2")
	jt=f1.read()
	f1.close()
	template_config=Template(jt)
	# for i in d1['nodes'].keys():
	#print("node ",i)
	data1={}
	data1['interfaces']=None
	data1['protocols']=None
	for j in d1['nodes'][i]['interfaces'].keys():
		#if 'mtu' in  d1['nodes'][i]['interfaces'][j].keys():
		#	data1=add_mtu(data1,j,d1['nodes'][i]['interfaces'][j]['mtu'])
		if 'family' in d1['nodes'][i]['interfaces'][j].keys():
			if 'inet' in d1['nodes'][i]['interfaces'][j]['family'].keys() and j != 'lo0':
				data1=add_into_protocols(data1,'lldp',j,"")
			if 'mpls' in d1['nodes'][i]['interfaces'][j]['family'].keys():
				data1=add_into_protocols(data1,'mpls',j,"")
				data1=add_mtu(data1,j,MTU)
			for k in d1['nodes'][i]['interfaces'][j]['family'].keys():
				if d1['nodes'][i]['interfaces'][j]['family'][k]:
					data1=add_into_interfaces(data1,j,k,d1['nodes'][i]['interfaces'][j]['family'][k])
				else:
					data1=add_into_interfaces(data1,j,k,True)
		if 'protocol' in d1['nodes'][i]['interfaces'][j].keys():
			for k in d1['nodes'][i]['interfaces'][j]['protocol'].keys():
				if k == 'mpls':
					pass
				elif k == 'isis':
					if d1['nodes'][i]['interfaces'][j]['protocol'][k] == 'ptp':
						option = 'point-to-point'
					elif d1['nodes'][i]['interfaces'][j]['protocol'][k] == 'passive':
						option = 'passive'
					else:
						option = ""
				else:
					option = ""
				#print("interface %s protocol %s option %s" %(j,k,option))
				data1=add_into_protocols(data1,k,j,option)
	print("uploading configuration into %s" %(i))
	config1 = template_config.render(data1)
	#print(d1)
	#print(config1)
	ip = d1['nodes'][i]['mgmt']['ip'][0].split('/')[0]
	user=d1['login']['user']
	passwd = d1['login']['password']
	#print("ip %s, user %s, password %s" %(ip,user,passwd))
	try:
		dev=Device(host=ip,user=user,password=passwd,gather_facts=False).open()
		#print(dev.facts)
		with Config(dev) as cu:  
			cu.load(config1,merge=True,format='text')
			cu.commit()
		dev.close()
	except jnpr.junos.exception.ConnectRefusedError:
		print("connection error")


def add_mtu(dt,intf,mtu):
	if not dt['interfaces']:
		dt['interfaces']={intf:None}
	if intf not in dt['interfaces'].keys():
		dt['interfaces'][intf]=None
	dt['interfaces'][intf]={'mtu':mtu}
	return dt

def add_into_interfaces(dt,intf,family,family_address):
	if not dt['interfaces']:
		dt['interfaces']={intf:None}
	if intf not in dt['interfaces'].keys():
		dt['interfaces'][intf]=None
	if not dt['interfaces'][intf]:
		dt['interfaces'][intf]={family:None}
	if family not in dt['interfaces'].keys():
		dt['interfaces'][intf][family]=family_address
	return dt

def add_into_protocols(dt,prot,intf,option):
	if not dt['protocols']:
		dt['protocols']={prot:None}
	if prot not in dt['protocols'].keys():
		dt['protocols'][prot]=None
	if not dt['protocols'][prot]:
		dt['protocols'][prot]={intf:None}
	if intf not in dt['protocols'][prot].keys():
		dt['protocols'][prot][intf]=None
	if option:
		dt['protocols'][prot][intf]=option
	return dt

def list_intf(i,d1,p1):
	retval={}
	for j in d1['nodes'][i]['interfaces'].keys():
		if 'protocols' in d1['nodes'][i]['interfaces'][j].keys():
			if p1 in d1['nodes'][i]['interfaces'][j]['protocols']:
				if d1['nodes'][i]['interfaces'][j]['protocols'][p1]:
					# retval.append({j: d1['nodes'][i]['interfaces'][j]['protocol'][p1]})
					retval[j] = d1['nodes'][i]['interfaces'][j]['protocols'][p1]
				else:
					#retval.append(j)
					retval[j]=None
	return retval 

def start_stop_domain(domName,cmd):
	conn = libvirt.open('qemu:///system')
	if conn == None:
		print('Failed to open connection to qemu:///system', file=sys.stderr)
		exit(1)
	for i in domName:
		dom=conn.lookupByName(i)
		#print("domain ",i)
		if cmd=='start':
			if dom.ID() != -1:
				print("VM %s is running with ID %d"  %(i,dom.ID()))
			else:
				dom.create()
				print("this domain %s will be started" %(i))
		elif cmd=='stop':
			if dom.ID():
				dom.destroy()
				print("this domain %s will be stopped" %(i))
			else:
				print("VM %s is not running"  %(i))
			
	conn.close()

def do_start_stopvm_sub1(d1,i):
	domName=[]
	if d1['nodes'][i]['type']=='vqfx':
		domName.append(d1['lab_name']+"-vcp-" + i)
		domName.append(d1['lab_name']+"-vpfe-" + i)
	elif d1['nodes'][i]['type']=='vmx':
		if dual_re(d1,i):
			domName.append(d1['lab_name']+"-vcp0-" + i)
			domName.append(d1['lab_name']+"-vcp1-" + i)
		else:
			domName.append(d1['lab_name']+"-vcp-" + i)
		domName.append(d1['lab_name']+"-vpfe-" + i)
	elif d1['nodes'][i]['type']=='vmx-n':
		domName.append(d1['lab_name']+"-vmx-" + i)
	else:
		domName.append(d1['lab_name']+"-" + i)
	return domName

def do_start_stopvm(d1):
	cmd=d1['config']['cmd']
	domain_to_start=d1['config']['nodes']
	domName=[]
	if domain_to_start == 'all':
		for i in d1['nodes'].keys():
			domName += do_start_stopvm_sub1(d1,i)
		print("domName ",domName)
		start_stop_domain(domName,cmd)	
	elif domain_to_start in d1['nodes'].keys():
		domName = do_start_stopvm_sub1(d1,domain_to_start)
		start_stop_domain(domName,cmd)
	else:
		print("Node ",domain_to_start, "it not available")
	
def defineXML(domName,xml_data):
	# xml_text=""
	# for i in xml:
	#	xml_text+=i
	xml = xml_data.decode("UTF-8")
	conn = libvirt.open('qemu:///system')
	if conn == None:
		print('Failed to open connection to qemu:///system', file=sys.stderr)
		exit(1)
#	print("before lookup",domName)
#	dom0 = conn.lookupByName(domName)
#	print("after lookup")
#	if dom0 == None:
	dom1 = conn.defineXML(xml)
	if dom1 == None:
		print('Failed to define a domain from an XML definition.', file=sys.stderr)
	conn.close()

def undefineVM(domName):
	print("Undefine domain ",domName)
	try:
		conn = libvirt.open('qemu:///system')
	except libvirt.libvirtError:
		print('Failed to open connection to qemu:///system', file=sys.stderr)
		sys.exit(1)

	try:
		dom = conn.lookupByName(domName)
		dom.undefine()
		conn.close()
		return True

	except libvirt.libvirtError:
		print('Failed to find the main domain')
		return False

def print_xml(xml):
	for i in xml:
		print(i)

def undefinevm(d1,i):
	lab_name=d1['lab_name']
	try:
		conn = libvirt.open('qemu:///system')
	except libvirt.libvirtError:
		print('Failed to open connection to qemu:///system', file=sys.stderr)
		sys.exit(1)

	if  d1['nodes'][i]['type'] == 'vmx':
		print("Undefine VM for Node ",i)
		try:
			if dual_re(d1,i):
				for re_idx in "01":
					node_name = lab_name + "-vcp" + re_idx + "-"+ i 
					dom0 = conn.lookupByName(node_name)
					undefineVM(node_name)
			else:
				node_name = lab_name + "-vcp-"+ i 
				dom0 = conn.lookupByName(node_name)
				undefineVM(node_name)
			node_name = lab_name + "-vpfe-"+ i
			dom0 = conn.lookupByName(node_name)
			undefineVM(node_name)

		except libvirt.libvirtError:
			print("VM %s is not defined" %(node_name))

	elif  d1['nodes'][i]['type'] == 'vqfx':
		print("Undefine VM for Node ",i)
		node_name = lab_name + "-vcp-"+ i
		try: 
			dom0 = conn.lookupByName(node_name)
			undefineVM(node_name)
		except libvirt.libvirtError:
			print("VM %s is not defined" %(node_name))
		
		node_name = lab_name + "-vpfe-"+ i
		try: 
			dom0 = conn.lookupByName(node_name)
			undefineVM(node_name)
		except libvirt.libvirtError:
			print("VM %s is not defined" %(node_name))

	elif  d1['nodes'][i]['type'] == 'vsrx':
		print("Undefine VM for Node ",i)
		node_name = lab_name + "-"+ i
		try: 
			dom0 = conn.lookupByName(node_name)
			undefineVM(node_name)
		except libvirt.libvirtError:
			print("VM %s is not defined" %(node_name))

	elif  d1['nodes'][i]['type'] == 'vrr':
		print("Undefine VM for Node ",i)
		node_name = lab_name + "-"+ i
		try: 
			dom0 = conn.lookupByName(node_name)
			undefineVM(node_name)
		except libvirt.libvirtError:
			print("VM %s is not defined" %(node_name))
	elif  d1['nodes'][i]['type'] == 'vmx-n':
		print("Undefine VM for Node ",i)
		node_name = lab_name + "-vmx-"+ i
		try: 
			dom0 = conn.lookupByName(node_name)
			undefineVM(node_name)
		except libvirt.libvirtError:
			print("VM %s is not defined" %(node_name))

def do_undefinevm(d1):
	vm = d1['config']['nodes']
	path1=d1['image_destination'] + "/" + d1['lab_name']
	lab_name=d1['lab_name']
	nodes=list(d1['nodes'].keys())
	if vm =='all':
		for i in nodes:
			undefinevm(d1,i)
		print("Deleting the image files")
		shutil.rmtree(path1)
	elif vm not in nodes:
		print("VM %s is not in the configuration file "%(vm))
	else:
		print("Undefine VM %s" %(vm))
		undefinevm(d1,vm)
		path1=path1 + "/" + vm
		if os.path.isdir(path1):
			shutil.rmtree(path1)

def definevm(d1,i):
	lab_name = d1['lab_name']
	try:
		conn = libvirt.open('qemu:///system')
	except libvirt.libvirtError:
		print('Failed to open connection to qemu:///system', file=sys.stderr)
		sys.exit(1)

	if  d1['nodes'][i]['type'] == 'vmx':
		print("Define VM for Node ",i)
		copy_vm_image(d1,i)
		if dual_re(d1,i):
			for re_idx in "01":
				try:
					domName = lab_name + "-vcp" + re_idx + "-" + i
					dom0 = conn.lookupByName(domName)
					print("VM %s is defined" %(domName))
				except libvirt.libvirtError as e:
					print("creating domain %s" %(domName))
					defineXML(domName,junos_vm_xml.create_vcp_vmx_xml(i,d1,re_idx))
		else:
			try:
				domName = lab_name + "-vcp-" + i
				dom0 = conn.lookupByName(domName)
			except libvirt.libvirtError as e:
				print("creating domain %s" %(domName))
				defineXML(domName,junos_vm_xml.create_vcp_vmx_xml(i,d1,"-1"))
		try:
			domName = lab_name + "-vpfe-" + i
			dom1 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError  as e:
			print("creating domain %s" %(domName))
			defineXML(domName,junos_vm_xml.create_vpfe_vmx_xml(i,d1))

	elif  d1['nodes'][i]['type'] == 'vqfx':
		print("Define VM for Node ",i)
		copy_vm_image(d1,i)
		domName = lab_name + "-vcp-" + i
		# defineXML(domName,junos_vm_xml.create_vcp_vqfx_xml(i,d1))
		try: 
			dom0 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError:
			print("creating domain %s" %(domName))
			# print("This is fail")
			defineXML(domName,junos_vm_xml.create_vcp_vqfx_xml(i,d1))
		domName = lab_name + "-vpfe-" + i
		try:
			dom0 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError:
			print("creating domain %s" %(domName))
			defineXML(domName,junos_vm_xml.create_vpfe_vqfx_xml(i,d1))
	elif  d1['nodes'][i]['type'] == 'vsrx':
		print("Define VM for Node ",i)
		copy_vm_image(d1,i)
		domName = lab_name + "-" + i
		try:
			dom0 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError:
			print("creating domain %s" %(domName))
			defineXML(domName,junos_vm_xml.create_vsrx_xml(i,d1))
	elif  d1['nodes'][i]['type'] == 'vrr':
		print("Define VM for Node ",i)
		copy_vm_image(d1,i)
		domName = lab_name + "-" + i
		try: 
			dom0 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError:
			print("creating domain %s" %(domName))
			defineXML(domName,junos_vm_xml.create_vrr_xml(i,d1))
	elif  d1['nodes'][i]['type'] == 'cvx':
		print("Define VM for Node ",i)
		copy_vm_image(d1,i)
		domName = lab_name + "-" + i
		try:
			dom0 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError:
			print("creating domain %s" %(domName))
			defineXML(domName,junos_vm_xml.create_cvx_xml(i,d1))
	elif  d1['nodes'][i]['type'] == 'vmx-n':
		print("Define VM for Node ",i)
		copy_vm_image(d1,i)
		domName = lab_name + "-vmx-" + i
		try:
			dom0 = conn.lookupByName(domName)
			print("VM %s is defined" %(domName))
		except libvirt.libvirtError:
			print("creating domain %s" %(domName))
			defineXML(domName,junos_vm_xml.create_vmx_xml(i,d1))

def do_definevm(d1):
	vm=d1['config']['nodes']
	nodes=list(d1['nodes'].keys())
	if vm=='all':
		for i in nodes:
			definevm(d1,i)
	elif vm not in nodes:
		print("VM is not defined the configuration")
	else:
		print("Creating VM %s" %(vm))
		definevm(d1,vm)

def copy_vm_image(d1,i):
	# nodes=d1['nodes'].keys()
	# for i in nodes:
	retval=True
	dest1=d1['image_destination'] + "/" +  d1['lab_name'] + "/" + i
	if os.path.isdir(dest1):
		print("directory %s exists" %(dest1))
		retval = False
	else:
		os.makedirs(dest1)
		print("copying image file for node ",i)
		if  d1['nodes'][i]['type'] == 'vmx':
			src_file =  d1['image_source'] + "/" + d1['files']['vmx']['dir'] + "/" + d1['files']['vmx']['pfe_file']
			dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" +  d1['files']['vmx']['pfe_file']
			shutil.copyfile(src_file, dst_file)
			if dual_re(d1,i):
				for re_idx in "01":
					os.makedirs(dest1 + "/re" + re_idx)
					for j in [d1['files']['vmx']['re_file'],'metadata-usb-re' + re_idx + '.img','vmxhdd.img']:
						src_file =  d1['image_source'] + "/" + d1['files']['vmx']['dir']  + "/" + j
						dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/re" +re_idx +"/" +  j
						shutil.copyfile(src_file, dst_file)
			else:
				for j in [d1['files']['vmx']['re_file'],'metadata-usb-re.img','vmxhdd.img']:
					src_file =  d1['image_source'] + "/" + d1['files']['vmx']['dir']  + "/" + j
					dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" +  j
					shutil.copyfile(src_file, dst_file)

		elif  d1['nodes'][i]['type'] == 'vqfx':
			for j in [d1['files']['vqfx']['re_file'],d1['files']['vqfx']['pfe_file']]:
				src_file =  d1['image_source'] +  "/" + d1['files']['vqfx']['dir'] + "/" + j
				dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" +j
				shutil.copyfile(src_file, dst_file)
		elif  d1['nodes'][i]['type'] == 'vsrx':
			src_file =  d1['image_source'] +  "/" + d1['files']['vsrx']['dir'] + "/" + d1['files']['vsrx']['re_file']
			dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" + d1['files']['vsrx']['re_file'] 
			shutil.copyfile(src_file, dst_file)
		elif  d1['nodes'][i]['type'] == 'vrr':
			src_file =  d1['image_source'] +  "/" + d1['files']['vrr']['dir'] + "/" + d1['files']['vrr']['re_file']
			dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" + d1['files']['vrr']['re_file'] 
			shutil.copyfile(src_file, dst_file)
		elif  d1['nodes'][i]['type'] == 'cvx':
			src_file =  d1['image_source'] +  "/" + d1['files']['cvx']['dir'] + "/" + d1['files']['cvx']['re_file']
			dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" + d1['files']['cvx']['re_file'] 
			shutil.copyfile(src_file, dst_file)
		elif  d1['nodes'][i]['type'] == 'vmx-n':
			src_file =  d1['image_source'] +  "/" + d1['files']['vmx']['dir'] + "/" + d1['files']['vmx']['nested']
			dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" + d1['files']['vmx']['nested'] 
			shutil.copyfile(src_file, dst_file)
	return retval

def dual_re(d1,i):
	retval = False
	if 'dual_re' in d1['nodes'][i].keys():
		if d1['nodes'][i]['dual_re']:
			retval = True
	return retval