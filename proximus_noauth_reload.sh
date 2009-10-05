#!/bin/sh

a=$(md5sum /etc/squid/noauth.txt)
./proximus_noauth.py

b=$(md5sum /etc/squid/noauth.txt)


if [ "$a" = "$b" ]
then
         echo " match"
else
         /etc/init.d/squid reload
fi
