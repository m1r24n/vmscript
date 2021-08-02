# installing LXD on alpine linux
1. edit repository to allow edge
sudo vi /etc/apk/repositories 
sudo apk update
sudo apk upgrade
2. install LXD
sudo apk add lxd
sudo apk add bridge
sudo rc-update add lxd
sudo rc-service lxd start
sudo rc-update add cgroups
sudo rc-service cgroups start
echo "session optional pam_cgfs.so -c freezer,memory,name=systemd,unified" | sudo tee -a /etc/pam.d/system-login
echo "lxc.idmap = u 0 100000 65536" | sudo tee -a  /etc/lxc/default.conf
echo "lxc.idmap = g 0 100000 65536" | sudo tee -a  /etc/lxc/default.conf
echo "root:100000:65536"  | sudo tee -a /etc/subuid
echo "root:100000:65536" | sudo tee -a /etc/subgid
sudo lxd init 

3. set vlan and bridge
/etc/network/interface
auto eth1
iface eth1 inet manual
mtu 1350
auto eth1.1091 
iface eth1.1091 inet manual
auto eth1.1092 
iface eth1.1092 inet manual
auto eth1.1093
iface eth1.1093 inet manual

auto lan91
iface lan91 inet manual
	bridge-ports eth1.1091
	bridge-stp 0
auto lan92
iface lan92 inet manual
	bridge-ports eth1.1092
	bridge-stp 0
auto lan93
iface lan93 inet manual
	bridge-ports eth1.1093
	bridge-stp 0

4. copy profile from default to purple91, purple92, purple93, and change the network bridge
sudo lxc profile copy default purple91
sudo lxc profile edit purple91

5. launch container 
sudo lxc launch images:alpine/edge -p purple91 alp1

6. connect to container
sudo lxc exec alp1 -- /bin/ash

7. add ssh server and enable it
sudo apk add openssh 
rc-update add openssh
rc-service sshd start
8. add user into container
adduser alpine




