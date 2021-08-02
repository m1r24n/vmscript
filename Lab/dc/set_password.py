#!/bin/env python3
import pexpect
from passlib.hash import md5_crypt
import yaml

def configure_junos(d1):
    my_hash = md5_crypt.hash(d1['password'])
    c1="virsh console " + d1['vm']
    s1=[
        "",
        "root",
        "cli",
        "edit",
        "set system host-name " + d1['hostname'],
        "set system root-authentication encrypted-password \"" + my_hash + "\"",
        "set system services ssh",
        "set system services netconf ssh",
        "set system login user " +  d1['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"",
        "set interfaces em0.0 family inet address " + d1['mgmt'],
        "set system management-instance",
        "set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + d1['gateway4'], 
        "commit",
        "exit",
        "exit",
        "exit"]
    e1=[
        "login:",
        "root@:RE:0%",
        "root>",
        "root#",
        "root#",
        "root#",
        "root#",
        "root#",
        "root#",
        "root#",
        "root#",
        "root#",
        "root@",
        "root@",
        "root@",
        "login:"]
    '''
    s1=[
        "",
        "root",
        "Juniper",
        "cli",
        "edit",
        "load factory-default",
        "set system host-name " + d1['hostname'],
        "set system root-authentication encrypted-password \"" + my_hash + "\"",
        "set system services ssh",
        "set system login user " +  d1['user'] + " class super-user authentication encrypted-password \"" + my_hash + "\"",
        "set interfaces em0.0 family inet address " + d1['mgmt'],
        "set system management-instance",
        "set routing-instances mgmt_junos routing-options static route 0.0.0.0/0 next-hop " + d1['gateway4'], 
        "commit",
        "exit",
        "exit",
        "exit"]
    e1=[
        "login:",
        "Password:",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "root@",
        "login:"]
'''
    print(len(s1),len(e1))
    if len(s1) == len(e1):
        p1=pexpect.spawn(c1)
        for i in list(range(len(s1))):
            #print("setting ",s1[i])
            p1.sendline(s1[i])
            p1.expect(e1[i])

def read_file(file1):
    retval=[]
    f1=open(file1)
    d1=yaml.load(f1,Loader=yaml.FullLoader)
    # d1=yaml.load(f1)
    f1.close()
    for i in d1['nodes'].keys():
        retval.append({
                'password':d1['login']['password'],
                'user':d1['login']['user'],
                'vm' : d1['prefix'] + i,
                'hostname' : i,
                'mgmt' : d1['nodes'][i]['mgmt'],
                'gateway4' : d1['gateway4']
        })
    return retval


# main program
filename="data1.yaml"
node = read_file(filename)
#print("node",node)
for i in node:
    print("configuring ",i['hostname'])
    configure_junos(i)
    print("done with ",i['hostname'])
