#!/bin/sh

# make a checksum of the file
a=$(md5sum /etc/squid/noauth.txt)

# get new file content
./proximus_noauth.py

if [ $? != 0 ]
then
   # something went wrong
   echo "Couldn't reload Proximus noauth config"
   exit 1
fi

# get new checksum
b=$(md5sum /etc/squid/noauth.txt)

# compare
if [ "$a" != "$b" ]
then
   # content has changed - so reload
   /etc/init.d/squid reload
fi
