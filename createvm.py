#!/usr/bin/env python3
# this is just a new file
# just another line
import sys
import os
import yaml
import junos_vm
# yaml.warnings({'YAMLLoadWarning': False})
config1=junos_vm.check_argv(sys.argv)
if config1:
	print("configuration ",config1)
	try:
		# load yaml file
		f1=open(config1['config_file'])
		d1=yaml.load(f1,Loader=yaml.FullLoader)
		f1.close()
		if config1['cmd'] == 'addbr':
			print("Creating bridges")
			junos_vm.do_bridge(d1,'addbr')
		elif config1['cmd'] == 'delbr':
			print("Deleting bridges")
			junos_vm.do_bridge(d1,'delbr')
		elif config1['cmd'] == 'definevm':
			print("Creating VM")
			junos_vm.do_definevm(d1)
		elif config1['cmd'] == 'undefinevm':
			print("Removing VM")
			junos_vm.do_undefinevm(d1)
		elif config1['cmd'] == 'start' or config1['cmd'] == 'stop':
			junos_vm.do_start_stopvm(d1,config1['cmd'],config1['vm'])

	except FileNotFoundError:
		print("where is the file")
	except PermissionError:
		print("Permission error")
else:
	print("")
