#!/usr/bin/php 
<?php

$config_file = '/etc/proximus/proximus.conf';
$filename_ip = "/etc/squid/noauth_ip.txt";
$filename_dn = "/etc/squid/noauth_dn.txt";
$dirty_config = false;

$config = parse_ini_file($config_file) or error("Can't open file $config_file");

# connect to mysql
$dbh = mysql_connect($config['db_host'], $config['db_user'], $config['db_pass']) or error("Unable to connect to MySQL");
$selected = mysql_select_db($config['db_name'],$dbh) or error("Could not select database");

updateFile($filename_ip, "SELECT sitename FROM noauth_rules WHERE type='IP'");
updateFile($filename_dn, "SELECT sitename FROM noauth_rules WHERE type='DN'");

mysql_close($dbh);

if ($dirty_config == true) {
   exec("/etc/init.d/squid status", $out, $retval);
   if ($retval == 0) {
      #echo "Reloading Squid config now...";
      openlog("Proximus-noauth", LOG_PID | LOG_PERROR, LOG_LOCAL0);
      syslog ( LOG_WARNING, "No-auth lists were updated. Reloading Squid config..." );
      exec("/etc/init.d/squid reload", $out, $retval);
   }
}



###############################
##### some proper functions

function stop($text, $code=0) {
   echo $text;
   exit($code);
}

function error($text) {
   stop($text, 1);
}

function updateFile($filename, $query) {
   global $dirty_config;

   $file_md5_pre = md5_file($filename);

   $file = fopen($filename, 'w') or error("Can't open file $filename");

   $result = mysql_query($query);
   while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
      fwrite($file, $row{'sitename'}."\n" );
      #echo $row{'sitename'}."\n";
   }

   fclose($file);

   if ( $file_md5_pre != md5_file($filename) ) {
      $dirty_config = true;
      #echo "MD5 changed for file $filename - reloading squid config later\n";
   }
}


?>
