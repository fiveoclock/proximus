#!/usr/bin/php 
<?php
# read config file
$config_file = '/etc/proximus/proximus.conf';
$config = parse_ini_file($config_file) or die("Can't open file $config_file");

# Open needed files
$filename_ip = "/etc/squid/noauth_ip.txt";
$filename_dn = "/etc/squid/noauth_dn.txt";
$file_ip = fopen($filename_ip, 'w') or die("Can't open file $filename_ip");
$file_dn = fopen($filename_dn, 'w') or die("Can't open file $filename_dn");

# connect to mysql
$dbh = mysql_connect($config['db_host'], $config['db_user'], $config['db_pass']) or die("Unable to connect to MySQL");
$selected = mysql_select_db($config['db_name'],$dbh) or die("Could not select database");


$result = mysql_query("SELECT sitename FROM noauth_rules WHERE type='IP'");
while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
   fwrite($file_ip, $row{'sitename'}."\n" );
   #echo $row{'sitename'}."\n";
}

$result = mysql_query("SELECT sitename FROM noauth_rules WHERE type='DN'");
while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
   fwrite($file_dn, $row{'sitename'}."\n" );
   #echo $row{'sitename'}."\n";
}


fclose($file_ip);
fclose($file_dn);


mysql_close($dbh);

