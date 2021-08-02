#!/usr/bin/env python3
import sys
import os
import pynetlinux
import subprocess
import libvirt
import traceback
import shutil 
import junos_vm_xml

# from jnpr.junos import Device
# from jnpr.junos.utils.config import Config
from passlib.hash import md5_crypt

#  change GROUP_FWD_MASK to 0x4000 if standard bridge kernel module is used
# 0x4000 is to allow only LLDP
# 0x400c is to allow only LLDP and LACP
# LACP Requires modified bridge kernel module

GROUP_FWD_MASK="0x400c"
#GROUP_FWD_MASK="0x4000"

def print_syntax():
	print("usage : createvm.py [-c filename] <command> <vm_name>")
	print("commands are : ")
	print("  addbr : to add bridge (requires sudo)")
	print("  delbr : to del bridge (requires sudo)")
	print("  definevm : to add VM into KVM hypervisor")
	print("  undefinevm : to remove VM from KVM hypervisor")
	print("  start : to start junos VM (it must be followed by VM name or all to start ) ")
	print("  stop : to stop junos VM (it must be followed by VM name or all to stop )")
	print("  config : to config junos VM (it must be followed by VM name or all to stop )")

def check_argv(argv):
	retval={}
	len_argv=len(argv)
	cmd_list=['addbr','delbr','definevm','undefinevm','stop','start','config']
	if '-c' not in argv:
		if not os.path.isfile("./lab.yaml"):
			print("file lab.yaml doesn't exist, please create one or define another file for configuration")
		else:
			retval['config_file']='lab.yaml'
			argv.pop(0)
	if '-c' in argv:
		index_c = argv.index("-c")
		if (len_argv - 1) == index_c:
			print_syntax()
		else:
			if not os.path.isfile(argv[index_c + 1]):
				print("file %s doesn't exist, please create one or define another file for configuration" % (argv[index_c + 1]))
			else:
				retval['config_file']=argv[index_c + 1]
				argv.pop(index_c + 1)
				argv.pop(index_c)
				argv.pop(0)

	if 'config_file' in retval.keys():
		len_1 = len(argv)
		len_2 = len(set(argv))
		if len_1 >  len_2:
			print("syntax error, there is duplicated argument")
			retval={}
		else:
			#print("argv ",argv)
			if argv[0] not in cmd_list:
				print("%s is not the correct command" %(argv[0]))
			else:
				if argv[0] in ['addbr','delbr']:
					if len(argv) != 1:
						retval={}
					else:
						retval['cmd'] = argv[0]
				else:
					retval['cmd']=argv[0]
					if len(argv)==2:
						retval['vm'] = argv[1]

	return retval

'''
def check_argv_old(argv):
	retval={}
	#cmd_list=['addbr','delbr','definevm','undefinevm','start','stop']
	cmd_list=['addbr','delbr','definevm','undefinevm']
	if len(argv) == 1:
		print_syntax()
	elif len(argv) == 2:
		if 'start' in argv or 'stop' in argv:
			print("command start/stop requires additional argument")
			print_syntax()
		else:
			if not os.path.isfile("./lab.conf"):
				print("file lab.conf doesn't exist, please create one or define another file for configuration")

			else:
				if argv[1] in cmd_list:
					retval['config_file']="lab.conf"
					retval['cmd']=argv[1]
					if argv[1] == 'stop' or argv[1]=='start':
						print("command start and stop requires additional argument")
						retval={}
				else:
					print("command " + argv[1] + " does not exist")
					print_syntax()
	elif len(argv)==3:
		if 'start' in argv or 'stop' in argv:
			if argv[1] == 'start' or argv[1] == 'stop':
				if not os.path.isfile('lab.conf'):
					print("file lab.conf doesn't exist, please create one")
				else:
					retval['config_file']='lab.conf'
					retval['vm']=argv[2]
					if 'start' in argv:
						retval['cmd']='start'
					if 'stop' in argv:
						retval['cmd']='stop'
		else:
			print("Syntax error")
			print_syntax()
	elif len(argv)==4:
		if 'start' in argv or 'stop' in argv:
			print("command start/stop requires additional argument")
			print_syntax()
		else:
			if "-c" in argv:
				index_c = argv.index("-c")
				if  index_c == (len(argv) - 1):
					print("syntax error")
					print_syntax()
				else:
					filename1=argv[argv.index("-c") + 1]
					if not os.path.isfile(filename1):
						print("file " + filename1 + " doesn't exist, please create one")
						print_syntax()
					else:
						retval['config_file']=filename1
						cmd_status=False
						for i in cmd_list:
							if i in argv:
								cmd1=argv.index(i)
								retval['cmd']=i
								cmd_status=True
								break
						if not cmd_status:
							print("command is not defined")
							print_syntax()
							retval={}
			else:
				print("Syntax error")
				print_syntax()
	elif len(argv)==5:
		if ('start' in argv) or ('stop' in argv): 
			if ('start' in argv and argv.index('start')==4) or ('stop' in argv and argv.index('stop') == 4):
				print("syntax error")
				print_syntax()
			elif "-c" not in argv:
				print("syntax error")
				print_syntax()
			else:
				index_c = argv.index("-c")
				if index_c == (len(argv) - 1):
					print("syntax error")
					print_syntax()
				else:
					filename1=argv[argv.index("-c") + 1]
					if not os.path.isfile(filename1):
						print("file " + filename1 + " doesn't exist, please create one")
					else:
						retval['config_file']=filename1
						if 'start' in argv:
							retval['cmd']='start'
							retval['vm']=argv[argv.index('start') + 1]
						if 'stop' in argv:
							retval['cmd']='stop'	
							retval['vm']=argv[argv.index('stop') + 1]
		else:
			print("syntax error")
			print_syntax()
		# if lab.conf is not defined dfine
	else:
		print("syntax error")
		print_syntax()

	return retval
'''

def check_existing_bridge(d1):
	if 'exist_bridge' in d1.keys():
		eb=d1['exist_bridge']
	else:
		eb=['']
	return eb

def do_bridge(d1,cmd1):
	#mgmt_intf=d1['lab_name']+ "-" +d1['mgmt']['intf']
	mgmt_intf=d1['mgmt']['intf']
	(mgmt_ip,mgmt_netmask)=d1['mgmt']['ip'].split("/")
	print("management ip ", mgmt_ip)
	print("management netmask ", mgmt_netmask)
	lab_name=d1['lab_name']
	nodes=list(d1['nodes'].keys())
	eb = check_existing_bridge(d1)
	if d1['mgmt']['intf'] not in eb:
		bridges=[mgmt_intf]
	else:
		bridges=[]
	for i in nodes:
		'''
		# original code
		for j in list(d1['nodes'][i]['interfaces'].values()):
		if j not in bridges:
				if j not in eb:
					bridges.append(lab_name + "-" + j)
		'''
		for j in list(d1['nodes'][i]['interfaces'].keys()):	
			if 'bridge' in d1['nodes'][i]['interfaces'][j].keys():
				if d1['nodes'][i]['interfaces'][j]['bridge'] not in eb:
					if d1['nodes'][i]['interfaces'][j]['bridge'] not in bridges:
						# bridges.append(lab_name + "-" + d1['nodes'][i]['interfaces'][j]['bridge'])
						bridges.append(d1['nodes'][i]['interfaces'][j]['bridge'])
	for i in nodes:
		if d1['nodes'][i]['type'] not in ['vsrx','cvx','vrr']:
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
				arg=[]
				arg.append("echo " + GROUP_FWD_MASK + " > " +  path1) 
				arg.append("echo 0 > " + path2) 
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

def create_isc_dhcpd_conf(d1):
	print("Create file ISC-DHCPD config")
	cfg=[]
	nodes=list(d1['nodes'].keys())
	for i in nodes:
		cfg.append("host " + d1['lab_name'] + "-" + i + " {")
		(ip_address,prefix1)=d1['nodes'][i]['fxp0']['ip'].split("/")
		cfg.append("   fixed-address " + ip_address + ";")
		cfg.append("   option tftp-server-name \"" + d1['dnsmasq']['tftp-server'] + "\";")
		cfg.append("   hardware ethernet " + d1['nodes'][i]['fxp0']['mac'] + ";")
		cfg.append("   option NEW_OP.config-file-name \"" + i + ".conf\";")
		cfg.append("}")
	oFile=open("dhcpd.conf","w")
	for line in cfg: oFile.write(line + '\n')
	oFile.close()

def create_junos_config(d1):
	pass

def create_dnsmasq_conf(d1):
	print("Create file dnsmasq.conf")
	cfg=[]
	nodes=list(d1['nodes'].keys())
	cfg.append("interface=" + d1['lab_name'] + "-" + d1['mgmt']['intf'])
	ip_low = d1['dnsmasq']['low']
	ip_high = d1['dnsmasq']['high']
	# (ip_low,ip_high) = iplib.subnet_low_high(d1['mgmt']['ip'])
	cfg.append("dhcp-range=" + ip_low + "," + ip_high + ",12h")
	(ip_gw,prefix) = d1['mgmt']['ip'].split("/")
	cfg.append("dhcp-option=150," + ip_gw)
	dmqprot=d1['dnsmasq']['protocol']
	cfg.append("dhcp-option=encap:43,3,\""+ dmqprot+"\"")
	for i in nodes:
		cfg.append("dhcp-option=tag:" + i + ",encap:43,1,\"" + i + ".conf\"")
		mac_address=d1['nodes'][i]['fxp0']['mac']
		(ip_address,prefix1)=d1['nodes'][i]['fxp0']['ip'].split("/")
		if d1['nodes'][i]['type']=='vqfx':
			cfg.append("dhcp-host=" + mac_address +  "," + ip_address +"," + i + ",set:" + i)
		else:
			cfg.append("dhcp-host=" + mac_address +  "," + ip_address +",set:" + i)
	oFile=open("dnsmasq.conf","w")
	for line in cfg: oFile.write(line + '\n')
	oFile.close()

def create_initial_config(d1):
	nodes=list(d1['nodes'].keys())
	for i in nodes:
		cfg=[]
		cfg.append("groups { ")
		cfg += create_config_base1(i,d1)
		cfg += create_config_base2(i,d1)
		cfg.append("}")
		cfg.append("apply-groups [ base1 base2 ];")
		filename=i + ".conf"
		print("configuration for node ",i," : ", filename)
		oFile=open(filename,"w")
		for line in cfg: oFile.write(line + '\n')
		oFile.close()

def create_config_base1(i,d1):
	cfg=[]
	t='''
system {
	host-name {{ hostname }};
	root-authentication {
		encrypted-password {{ enc_passwd }};
		{% if ssh_key -%}
			ssh-rsa {{ ssh_key }};
		{% endif% }
	}
	login {
		user admin {
			class super-suser;
			authentication {
				encrypted-password {{ enc_passwd}};
				% if ssh_key -%}
					ssh-rsa {{ ssh_key }};
				{% endif% }
			}
		}
	}
	services {
		ssh;
		netconf {
			ssh;
		}
	}
}
	'''
	if d1['nodes'][i]['type'] in ['vmx','vqfx','vrr']:
		cfg.append("\tbase1 {")
		cfg.append("\t\tsystem {")
		cfg.append("\t\t\thost-name " + i + ";")
		cfg.append("\t\t\troot-authentication {")
		cfg.append("\t\t\t\tencrypted-password \"" + md5_crypt.encrypt((d1['login']['root_password'])) + "\";")
		if d1['login']['ssh_key']:
			cfg.append("\t\t\t\tssh-rsa \"" + d1['login']['ssh_key'] + "\";")
		cfg.append("\t\t\t}")
		cfg.append("\t\t\tlogin {\n\t\tuser admin {\n\t\t\tclass super-user;")
		cfg.append("\t\t\t\tauthentication {")
		cfg.append("\t\t\t\t\tencrypted-password \"" + md5_crypt.encrypt((d1['login']['password'])) + "\";")
		if d1['login']['ssh_key']:
			cfg.append(" \t\t\t\t\tssh-rsa \"" + d1['login']['ssh_key'] + "\";")
		cfg.append("\t\t\t\t}\n\t\t\t}\n\t\t}")
		cfg.append("\t\t\tservices {\n\t\t\t\tssh;\n\t\t\t\tnetconf {\n\t\t\t\t\tssh;")
		cfg.append("\t\t\t\t}\n\t\t\t}")
		cfg.append("\t\t\tsyslog {\n\t\t\t\tuser * {\n\t\t\t\t\t any emergency;")
		cfg.append("\t\t\t\t\t}")
		cfg.append("\t\t\t\tfile messages {\n\t\t\t any notice;\n\t\t\t authorization info;\n\t\t}")
		cfg.append("\t\tfile interactive-commands {\n\t\t\t interactive-commands any;\n\t\t}")
		cfg.append("\t}")
		if d1['nodes'][i]['type'] == 'vqfx':
			cfg.append("\textensions {\n\t\tproviders {\n\t\t\tjuniper {\n\t\t\t\tlicense-type juniper deployment-scope commercial;")
			cfg.append("\t\t\t}")
			cfg.append("\t\t\tchef {\n\t\t\t\tlicense-type juniper deployment-scope commercial;")
			cfg.append("\t\t\t}\n\t\t}\n\t}")
		cfg.append("}")

		if d1['nodes'][i]['type'] == 'vmx':
			cfg.append("chassis {\n\tfpc 0 {\n\t\tlite-mode;\n\t}\n\tnetwork-services enhanced-ip;")
			cfg.append("}")
			cfg.append("interfaces {\n\tfxp0 {\n\t\tunit 0 {\n\t\t\tfamily inet {")
			cfg.append("\t\t\t\taddress " + d1['nodes'][i]['fxp0']['ip'] + ";")
			cfg.append("\t\t\t}\n\t\t}\n\t}\n}")
		if d1['nodes'][i]['type'] == 'vqfx':
			cfg.append("interfaces {\n\tem0 {\n\t\tunit 0 {\n\t\t\tfamily inet {")
			cfg.append("\t\t\t\taddress " + d1['nodes'][i]['fxp0']['ip'] + ";")
			cfg.append("\t\t\t}\n\t\t}\n\t}\n}")
			cfg.append("interfaces {\n\tem1 {\n\t\tunit 0 {\n\t\t\tfamily inet {")
			cfg.append("\t\t\t\taddress 169.254.0.2/24;")
			cfg.append("\t\t\t}\n\t\t}\n\t}\n}")
			cfg.append("forwarding-options {\n\tstorm-control-profiles default {\n\t\tall;\n\t}\n}")
			cfg.append("protocols {\n\tigmp-snooping {\n\t\tvlan default;\n\t}\n}")
			cfg.append("vlans {\n\tdefault {\n\t\tvlan-id 1;\n\t}\n}")
		if d1['nodes'][i]['type'] == 'vsrx':
			cfg.append("interfaces {\n\tfxp0 {\n\t\tunit 0 {\n\t\t\tfamily inet {")
			cfg.append("\t\t\t\taddress " + d1['nodes'][i]['fxp0']['ip'] + ";")
			cfg.append("\t\t\t}\n\t\t}\n\t}\n}")
		cfg.append("\t}")
	return cfg 

def create_config_base2(i,d1):
	cfg=[]
	if d1['nodes'][i]['type'] in ['vmx','vqfx','vrr']:
		cfg.append("\tbase2 {")
		# start of interfaces configuration
		cfg.append("\t\tinterfaces {")
		for j in d1['nodes'][i]['interfaces'].keys():
			t1 = d1['nodes'][i]['interfaces'][j].keys()
			cfg.append("\t\t\t %s {" % (j))
			if 'description' in t1:
				cfg.append("\t\t\t\t description \"%s\";" %(d1['nodes'][i]['interfaces'][j]['description']))
			if 'mtu' in t1:
				cfg.append("\t\t\t\t mtu %d;" %(d1['nodes'][i]['interfaces'][j]['mtu']))
			cfg.append("\t\t\t\t unit 0 {")
			if 'family' in t1:
				t2 = d1['nodes'][i]['interfaces'][j]['family'].keys()
				if 'inet' in t2:
					cfg.append("\t\t\t\t\t family inet {")
					cfg.append("\t\t\t\t\t\t address " + d1['nodes'][i]['interfaces'][j]['family']['inet'] + ";")
					cfg.append("\t\t\t\t\t }")
				if 'inet6' in t2:
					cfg.append("\t\t\t\t\t family inet6 {")
					cfg.append("\t\t\t\t\t\t address " + d1['nodes'][i]['interfaces'][j]['family']['inet6'] + ";")
					cfg.append("\t\t\t\t\t }")
				if 'iso' in t2:
					if j == 'lo0':
						cfg.append("\t\t\t\t\t family iso {")
						cfg.append("\t\t\t\t\t\t address " + d1['nodes'][i]['interfaces'][j]['family']['iso'] + ";")
						cfg.append("\t\t\t\t\t }")
					else:
						cfg.append("\t\t\t\t\t family iso;")
				if 'mpls' in t2:
					cfg.append("\t\t\t\t\t family mpls;")
			cfg.append("\t\t\t\t}")
			cfg.append("\t\t\t }")
		cfg.append("\t\t}")
		# end of interfaces configuration
		
		# ldp configuration
		lldp_intf=list_intf(i,d1,'lldp')
		mpls_intf=list_intf(i,d1,'mpls')
		rsvp_intf=list_intf(i,d1,'rsvp')
		ldp_intf=list_intf(i,d1,'ldp')
		isis_intf=list_intf(i,d1,'isis')

		if lldp_intf or mpls_intf or ldp_intf:
		# start of protocols configuration
			cfg.append("\t\tprotocols {")
			if lldp_intf:
				cfg.append("\t\t\tlldp {")
				for i in lldp_intf.keys():
					cfg.append("\t\t\t\t interface %s;" % (i))
				cfg.append("\t\t\t}")
			if rsvp_intf:
				cfg.append("\t\t\trsvp {")
				for i in lldp_intf.keys():
					cfg.append("\t\t\t\t interface %s;" % (i))
				cfg.append("\t\t\t}")
			if mpls_intf:
				cfg.append("\t\t\tmpls {")
				for i in mpls_intf.keys():
					cfg.append("\t\t\t\t interface %s.0;" % (i))
				cfg.append("\t\t\t}")
			if ldp_intf:
				cfg.append("\t\t\tldp {")
				for i in ldp_intf.keys():
					cfg.append("\t\t\t\t interface %s.0;" % (i))
				cfg.append("\t\t\t}")
			if isis_intf:
				cfg.append("\t\t\tisis {")
				for i in isis_intf.keys():
					if isis_intf[i] == None:
						cfg.append("\t\t\t\t interface %s.0;" % (i))
					else:
						cfg.append("\t\t\t\t interface %s.0 {" % (i))
						if isis_intf[i] == 'passive':
							net_type = 'passive'
						elif isis_intf[i] == 'p2p':
							net_type = 'point-to-point'
						cfg.append("\t\t\t\t\t %s;" % (net_type))
						cfg.append("\t\t\t\t}")
				cfg.append("\t\t\t}")


		# end of protocols configuration
			cfg.append("\t\t}")
		
		cfg.append("\t}")
	return cfg

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
		if cmd=='start':
			dom.create()
			print("this domain %s will be started" %(i))
		elif cmd=='stop':
			dom.destroy()
			print("this domain %s will be stopped" %(i))
	conn.close()

def do_start_stopvm(d1,cmd,domain_to_start):
	domName=[]
	if domain_to_start == 'all':
		for i in d1['nodes'].keys():
			if d1['nodes'][i]['type']=='vmx' or d1['nodes'][i]['type']=='vqfx':
				domName.append(d1['lab_name']+"-vcp-" + i)
				domName.append(d1['lab_name']+"-vpfe-" + i)
			else:
				domName.append(d1['lab_name']+"-" + i)
		start_stop_domain(domName,cmd)
	elif domain_to_start in d1['nodes'].keys():
		if d1['nodes'][domain_to_start]['type']=='vmx' or d1['nodes'][domain_to_start]['type']=='vqfx':
			domName.append(d1['lab_name']+"-vcp-" + domain_to_start)
			domName.append(d1['lab_name']+"-vpfe-" + domain_to_start)
		else:
				domName.append(d1['lab_name']+"-" + domain_to_start)
		if cmd=='start':
			print("these domain will be started : ",domName)
		elif cmd=='stop':
			print("these domain will be stoped : ",domName)
		start_stop_domain(domName,cmd)

	else:
		print("Node ",domain_to_start, "it not avalailable")
	
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
	conn = libvirt.open('qemu:///system')
	if conn == None:
		print('Failed to open connection to qemu:///system', file=sys.stderr)
		exit(1)
	dom = conn.lookupByName(domName)
	if dom == None:
		print('Failed to find the domain '+domName, file=sys.stderr)
		exit(1)
	dom.undefine()
	conn.close()

def print_xml(xml):
	for i in xml:
		print(i)

def do_undefinevm(d1):
	nodes=list(d1['nodes'].keys())
	lab_name=d1['lab_name']
	for i in nodes:
		if  d1['nodes'][i]['type'] == 'vmx':
			print("Undefine VM for Node ",i)
			node_name = lab_name + "-vcp-"+ i
			undefineVM(node_name)
			node_name = lab_name + "-vpfe-"+ i
			undefineVM(node_name)
		elif  d1['nodes'][i]['type'] == 'vqfx':
			print("Undefine VM for Node ",i)
			node_name = lab_name + "-vcp-"+ i
			undefineVM(node_name)
			node_name = lab_name + "-vpfe-"+ i
			undefineVM(node_name)
		elif  d1['nodes'][i]['type'] == 'vsrx':
			print("Undefine VM for Node ",i)
			node_name = lab_name + "-"+ i
			undefineVM(node_name)
		elif  d1['nodes'][i]['type'] == 'vrr':
			print("Undefine VM for Node ",i)
			node_name = lab_name + "-"+ i
			undefineVM(node_name)
	path1=d1['image_destination'] + "/" + d1['lab_name'] 	
	print("Deleting the image files")
	shutil.rmtree(path1)	

def do_definevm(d1):
	nodes=list(d1['nodes'].keys())
	mgmt = d1['lab_name'] + "-" + d1['mgmt']['intf']
	lab_name = d1['lab_name']
	print("Copying image files")
	copy_vm_image(d1)
	for i in nodes:
		if  d1['nodes'][i]['type'] == 'vmx':
			print("Define VM for Node ",i)
			domName = lab_name + "-vcp-" + i
			defineXML(domName,junos_vm_xml.create_vcp_vmx_xml(i,d1))
			domName = lab_name + "-vpfe-" + i
			defineXML(domName,junos_vm_xml.create_vpfe_vmx_xml(i,d1))
		elif  d1['nodes'][i]['type'] == 'vqfx':
			print("Define VM for Node ",i)
			domName = lab_name + "-vcp-" + i
			defineXML(domName,junos_vm_xml.create_vcp_vqfx_xml(i,d1))
			domName = lab_name + "-vpfe-" + i
			defineXML(domName,junos_vm_xml.create_vpfe_vqfx_xml(i,d1))
		elif  d1['nodes'][i]['type'] == 'vsrx':
			domName = lab_name + "-" + i
			print("Define VM for Node ",i)
			defineXML(domName,junos_vm_xml.create_vsrx_xml(i,d1))
		elif  d1['nodes'][i]['type'] == 'vrr':
			print("Define VM for Node ",i)
			domName = lab_name + "-" + i
			defineXML(domName,junos_vm_xml.create_vrr_xml(i,d1))
		elif  d1['nodes'][i]['type'] == 'cvx':
			print("Define VM for Node ",i)
			domName = lab_name + "-" + i
			defineXML(domName,junos_vm_xml.create_cvx_xml(i,d1))
	#print("creating initial config for nodes. \nCopy these files into the home directory of the TFTP.\nDO THIS BEFORE STARTING the VM ")
	#create_initial_config(d1)
	#print("creating DNSMASQ configuration. \nCopy or append this files into the DNSMASQ server configuration and restart dnsmasq server.\nDO THIS BEFORE STARTING the VM ") 
	#create_dnsmasq_conf(d1)
	#print("creating ISC-DCHCP configuration. \nCopy or append this files into the ISC-DHCP server configuration and restart dnsmasq server.\nDO THIS BEFORE STARTING the VM ")
	#create_isc_dhcpd_conf(d1)

def copy_vm_image(d1):
	nodes=d1['nodes'].keys()
	for i in nodes:
		dest1=d1['image_destination'] + "/" +  d1['lab_name'] + "/" + i
		os.makedirs(dest1)
		print("copying image file for node ",i)
		if  d1['nodes'][i]['type'] == 'vmx':
			for j in [d1['files']['vmx']['re_file'],d1['files']['vmx']['pfe_file'],'metadata-usb-re.img','vmxhdd.img']:
				src_file =  d1['image_source'] + "/" + d1['files']['vmx']['dir'] + "/" + j
				dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" +  j
				shutil.copyfile(src_file, dst_file)
		elif  d1['nodes'][i]['type'] == 'vqfx':
			for j in [d1['files']['vqfx']['re_file'],d1['files']['vqfx']['pfe_file']]:
				src_file =  d1['image_source'] +  "/" + d1['files']['vqfx']['dir'] + "/" + j
				dst_file = d1['image_destination'] + "/" + d1['lab_name'] + "/" + i + "/" +j
				shutil.copyfile(src_file, dst_file)
		elif  d1['nodes'][i]['type'] == 'vsrx':
			src_file =  d1['image_source'] +  "/" + d1['files']['vmx']['dir'] + "/" + d1['files']['vsrx']['re_file']
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

