#!/usr/bin/env python3
import sys
import os
import yaml
from jinja2 import Template
import jnpr.junos
from jnpr.junos import Device
from jnpr.junos.utils.config import Config

def print_syntax():
    print("usage : config_junos.py -c <config_file>")

def check_argv(argv):
    retval = {}
    if len(argv) != 3:
        print_syntax()
        return retval
    else:
        if '-c' not in argv:
            print("usage : config_junos.py -c <config_file>")
            return retval
        if argv.index('-c') != 1:
            print("usage : config_junos.py -c <config_file>")
            return retval
        else:
            filename = argv[2]
            try:
                f1=open(filename)
                retval=yaml.load(f1,Loader=yaml.FullLoader)
                f1.close()
                return retval
            except FileNotFoundError:
                print("where is the file")
            except PermissionError:
                print("Permission error")

def set_pcc(d1):
    if 'pcc_server' not in d1.keys():
        print("PCC is not configured")
    else:
        print("Setting PCC")
        print("PCC Server {}".format(d1['pcc_server']))
        template_pcc=Template('''set protocols mpls lsp-external-controller pccd 
set protocols pcep pce paragon local-address {{ loopback }}
set protocols pcep pce paragon destination-ipv4-address {{ pcc_server }}
set protocols pcep pce paragon destination-port 4189 
set protocols pcep pce paragon pce-type active
set protocols pcep pce paragon pce-type stateful
set protocols pcep pce paragon lsp-provisioning''')
        d2 = {'pcc_server' : d1['pcc_server'] }
        d2.update({'loopback' : {}})
        for i in d1['nodes'].keys():
            if 'lo0' in d1['nodes'][i]['interfaces'].keys():
                d2['loopback'] = d1['nodes'][i]['interfaces']['lo0']['family']['inet'].split('/')[0]
                print("uploading config into router ",i)
                config1=template_pcc.render(d2)
                ip = d1['nodes'][i]['mgmt']['ip'].split('/')[0]
                user=d1['login']['user']
                passwd = d1['login']['password']
                #print("ip %s, user %s, password %s" %(ip,user,passwd))
                try:
                    dev=Device(host=ip,user=user,password=passwd,gather_facts=False).open()
                    #print(dev.facts)
                    with Config(dev) as cu:  
                        cu.load(config1,merge=True,format='set')
                        cu.commit()
                    dev.close()
                except jnpr.junos.exception.ConnectRefusedError:
                    print("connection error")


def set_jti(d1):
    template_jti=Template('''
set services analytics streaming-server hb remote-address {{ pcc_server }}
set services analytics streaming-server hb remote-port 4000
set services analytics export-profile ns local-address {{ loopback }}
set services analytics export-profile ns local-port 4001
set services analytics export-profile ns reporting-rate 30
set services analytics export-profile ns format gpb
set services analytics export-profile ns transport udp
set services analytics sensor ifd server-name hb
set services analytics sensor ifd export-name ns
set services analytics sensor ifd resource /junos/system/linecard/interface/
set services analytics sensor ifd export-to-routing-engine
set services analytics sensor ifl server-name hb
set services analytics sensor ifl export-name ns
set services analytics sensor ifl resource /junos/system/linecard/interface/logical/usage/
set services analytics sensor ifl export-to-routing-engine
set services analytics sensor lsp server-name hb
set services analytics sensor lsp export-name ns
set services analytics sensor lsp resource /junos/services/label-switched-path/usage/
set services analytics sensor lsp export-to-routing-engine
set services analytics sensor sr-te-color server-name hb
set services analytics sensor sr-te-color export-name ns
set services analytics sensor sr-te-color resource /junos/services/segment-routing/traffic-engineering/ingress/usage/
set services analytics sensor sr-te-color export-to-routing-engine
set services analytics sensor sid server-name hb
set services analytics sensor sid export-name ns
set services analytics sensor sid resource /junos/services/segment-routing/sid/usage/
set services analytics sensor sid export-to-routing-engine
set services analytics sensor sr-te-tunnels server-name hb
set services analytics sensor sr-te-tunnels export-name ns
set services analytics sensor sr-te-tunnels resource /junos/services/segment-routing/traffic-engineering/tunnel/ingress/usage/
set services analytics sensor sr-te-tunnels export-to-routing-engine
{% for intf in interfaces %}
set services rpm probe northstar-ifl test {{intf}} probe-type icmp-ping-timestamp
set services rpm probe northstar-ifl test {{intf}} target address {{ interfaces[intf].peer_IP }}
set services rpm probe northstar-ifl test {{intf}} probe-count 15
set services rpm probe northstar-ifl test {{intf}} probe-interval 1
set services rpm probe northstar-ifl test {{intf}} test-interval 20
set services rpm probe northstar-ifl test {{intf}} source-address {{ interfaces[intf].source_IP }}
set services rpm probe northstar-ifl test {{intf}} history-size 512
set services rpm probe northstar-ifl test {{intf}} moving-average-size 60
set services rpm probe northstar-ifl test {{intf}} traps test-completion
set services rpm probe northstar-ifl test {{intf}} destination-interface {{ intf }}
set services rpm probe northstar-ifl test {{intf}} one-way-hardware-timestamp
{% endfor %}


    ''')
    d2 = {'pcc_server' : d1['pcc_server'] }
    d2.update({'loopback' : {}})
    d2.update({'interfaces' : {}})
    for i in d1['nodes'].keys():
        if 'lo0' in d1['nodes'][i]['interfaces'].keys():
            d2['loopback'] = d1['nodes'][i]['interfaces']['lo0']['family']['inet'].split('/')[0]
            for j in d1['nodes'][i]['interfaces'].keys():
                if 'ge' in j and 'family' in d1['nodes'][i]['interfaces'][j].keys():
                    if 'inet' in d1['nodes'][i]['interfaces'][j]['family'].keys():
                        source_IP = d1['nodes'][i]['interfaces'][j]['family']['inet'].split('/')[0]
                        byte0,byte1,byte2,byte3 = source_IP.split('.')
                        byte3_int = int(byte3)
                        if (byte3_int % 2) == 0:
                            byte3_int +=1
                        else:
                            byte3_int -=1
                        byte3=str(byte3_int)
                        peer_IP = "{}.{}.{}.{}".format(byte0,byte1,byte2,byte3)
                        d2['interfaces'].update({j : {'source_IP' : source_IP,'peer_IP' : peer_IP}})
                        
                        #d2['interfaces'].update({j : {{'source_IP' : source_IP},{'peer_IP' : peer_IP}}})
                        #d2['interfaces'][j].update({'source_IP' : source_IP})
                        #d2['interfaces'][j].update({'peer_IP' : peer_IP})
                    
            print("uploading config into router ",i)
            config1=template_jti.render(d2)
            ip = d1['nodes'][i]['mgmt']['ip'].split('/')[0]
            user=d1['login']['user']
            passwd = d1['login']['password']
            #print(d2)
            #print(config1)
            #print("ip %s, user %s, password %s" %(ip,user,passwd))
            try:
                dev=Device(host=ip,user=user,password=passwd,gather_facts=False).open()
                #print(dev.facts)
                with Config(dev) as cu:  
                    cu.load(config1,merge=True,format='set')
                    cu.commit()
                dev.close()
            except jnpr.junos.exception.ConnectRefusedError:
                print("connection error")

# main program 
d1 = check_argv(sys.argv)
if d1:
    set_pcc(d1)
    set_jti(d1)