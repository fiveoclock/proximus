#!/bin/sh

# make a checksum of the file
f_ip1=$(md5sum /etc/squid/noauth_ip.txt)
f_dn1=$(md5sum /etc/squid/noauth_dn.txt)

# get new file content
/usr/share/proximus/proximus_noauth.php

if [ $? != 0 ]
then
   # something went wrong
   echo "Couldn't reload Proximus noauth config"
   exit 1
fi

# get new checksum
f_ip2=$(md5sum /etc/squid/noauth_ip.txt)
f_dn2=$(md5sum /etc/squid/noauth_dn.txt)

# compare
if [ "$f_ip1 $f_dn1" != "$f_ip2 $f_dn2" ]
then
   # content has changed - so reload
   /etc/init.d/squid reload
fi
