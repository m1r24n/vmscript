#!/bin/bash
BRIDGE=jktge0
INTF=veth0
NAMESPACE=jkt
IPADDR=192.168.101.10/24
GW=192.168.101.1
INTFBR=${INTF}br
sudo ip link add ${INTF} type veth peer ${INTFBR}
sudo ip link set dev ${INTFBR} up
sudo ip link set ${INTFBR} master ${BRIDGE}
sudo ip netns add ${NAMESPACE}
sudo ip link set ${INTF} netns ${NAMESPACE}
sudo ip netns exec ${NAMESPACE} ip link set dev lo up
sudo ip netns exec ${NAMESPACE} ip addr add dev ${INTF} ${IPADDR}
sudo ip netns exec ${NAMESPACE} ip link set dev ${INTF} up
sudo ip netns exec ${NAMESPACE} ip route add default via ${GW}
echo "alias ${NAMESPACE}=\"sudo ip netns exec ${NAMESPACE} \""


BRIDGE=sbyge0
INTF=veth1
NAMESPACE=sby
IPADDR=192.168.102.10/24
GW=192.168.102.1
INTFBR=${INTF}br
sudo ip link add ${INTF} type veth peer ${INTFBR}
sudo ip link set dev ${INTFBR} up
sudo ip link set ${INTFBR} master ${BRIDGE}
sudo ip netns add ${NAMESPACE}
sudo ip link set ${INTF} netns ${NAMESPACE}
sudo ip netns exec ${NAMESPACE} ip link set dev lo up
sudo ip netns exec ${NAMESPACE} ip addr add dev ${INTF} ${IPADDR}
sudo ip netns exec ${NAMESPACE} ip link set dev ${INTF} up
sudo ip netns exec ${NAMESPACE} ip route add default via ${GW}
echo "alias ${NAMESPACE}=\"sudo ip netns exec ${NAMESPACE} \""
