#!/bin/env python3
import pexpect
from passlib.hash import md5_crypt
import yaml
import sys

def configure_junos(d1):
    for i in d1:
        my_hash_root = md5_crypt.hash(i['root_password'])
        my_hash = md5_crypt.hash(i['password'])
        c1="virsh console " + i['vm']
        print("configuring ",i['vm'])
        if i['type'] == 'vqfx':
            s_e = [
                    ["","login:"],
                    ["root", "root@:RE:0%"],
                    ["cli","root#"],
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
        elif i['type'] == 'vmx':
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


def create_data(d1):
    retval=[]
    for i in d1['nodes'].keys():
        retval.append({
                'password':d1['login']['password'],
                'root_password':d1['login']['root_password'],
                'user':d1['login']['user'],
                'vm' : d1['lab_name'] +"-vcp-" +  i,
                'hostname' : i,
                'mgmt' : d1['nodes'][i]['mgmt']['ip'],
                'gateway4' : d1['mgmt']['ip'].split('/')[0],
                'type' :d1['nodes'][i]['type']
        })
    return retval

def print_syntax():
    print("syntax error")
    print("set_password -c <config_file>") 

def check_arg(argv):
    retval=None
    if len(argv) != 3:
        print_syntax()
    elif '-c' not in sys.argv:
        print_syntax()
    else:
        index_c = argv.index("-c")
        if  index_c == (len(sys.argv) - 1):
            print_syntax()
        else:
            filename = argv[argv.index('-c') + 1]
            retval=filename
    return retval


# main program
filename=check_arg(sys.argv)
if filename:
    try:
        f1=open(filename)
        d1=yaml.load(f1,Loader=yaml.FullLoader)
        f1.close()
        d2=create_data(d1)
        configure_junos(d2)
    except FileNotFoundError:
        print("where is the file ",filename)

    except PermissionError:
        print("Permission error")

