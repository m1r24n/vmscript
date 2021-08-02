#!/bin/bash
LB=1
for i in acs p1 vbng p2 pe1
do
	ssh admin@10.1.100.15${LB} "show configuration" > ${i}.conf
	LB=`expr ${LB} + 1`
done
