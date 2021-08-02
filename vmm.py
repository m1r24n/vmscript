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
	#print("configuration ",config1)
	try:
		# load yaml file
		if 'config_file' in config1.keys():
			d1=junos_vm.read_config(config1)
			if 'cmd' in d1['config'].keys():
				# if config1['cmd'] == 'config':
				if d1['config']['cmd'] == 'config':
					junos_vm.config_junos(d1)
				elif d1['config']['cmd'] == 'init_vm':
					junos_vm.init_vm(d1)
				elif d1['config']['cmd'] == 'addbr' or d1['config']['cmd'] == 'delbr':
					if d1['config']['cmd'] == 'addbr':
						print("Creating bridges")
					if d1['config']['cmd'] == 'delbr':
						print("Deleting bridges")
					junos_vm.do_bridge(d1)
				elif d1['config']['cmd'] == 'definevm':
					print("Creating VM")
					junos_vm.do_definevm(d1)
				elif d1['config']['cmd'] == 'undefinevm':
					print("Removing VM")
					junos_vm.do_undefinevm(d1)
				elif d1['config']['cmd'] == 'start' or d1['config']['cmd'] == 'stop':
					# junos_vm.do_start_stopvm(d1,config1['cmd'],config1['vm'])
					junos_vm.do_start_stopvm(d1)
				elif d1['config']['cmd'] == 'config4ns':
					# junos_vm.do_start_stopvm(d1,config1['cmd'],config1['vm'])
					junos_vm.config4ns(d1)
			else:
				print("argument 'cmd' is not defined yet")

	except FileNotFoundError:
		print("where is the file")
	except PermissionError:
		print("Permission error")
else:
	junos_vm.print_syntax()
