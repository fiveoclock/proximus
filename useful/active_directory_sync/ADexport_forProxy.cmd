rem Export all Domain Users which are member of "Internet-access"
cscript C:\Tools\ADexport_forProxy.vbs dc-vie.dom1.dom.net ALL 2 0

c:
cd \Tools\Proxy
copy User_dom1.csv dom1_User.dat /b
"C:\Perl\bin\perl.exe" C:\Tools\export_proximus.pl >> c:\Tools\Proxy\User.log

del c:\Tools\Proxy\*.csv
