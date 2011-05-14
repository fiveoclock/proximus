rem Export all Domain Users which are member of "MM-Internet"
cscript C:\Tools\ADexport_forProxy.vbs dc-vie-50.mmk.mmdom.net ALL 2 0

c:
cd \Tools\Proxy
copy User_mmk.csv MM_User.dat /b
"C:\Perl\bin\perl.exe" C:\Tools\export_mm_proximus.pl >> c:\Tools\Proxy\User.log

del c:\Tools\Proxy\*.csv
