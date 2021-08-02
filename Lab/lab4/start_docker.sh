docker run --rm --detach --name crpd01 -h crpd01 --net=bridge --privileged -v crpd01-config:/config -v crpd01-varlog:/var/log -p 179:179 -p 65022:22 -it crpd:21.2R1.10
