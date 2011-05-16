#!/usr/bin/php 
<?php

openlog("Proximus-noauth", LOG_PID | LOG_INFO, LOG_LOCAL0);
$config_file = '/etc/proximus/proximus.conf';
$squid_init_script = "/etc/init.d/squid";
$filename_ip = "/etc/squid/noauth_ip.txt";
$filename_dn = "/etc/squid/noauth_dn.txt";
$hostname = trim(`hostname -f`);
$dirty_config = false;

$config = parse_ini_file($config_file) or error("Can't open file $config_file");

# connect to mysql
$dbh = mysql_connect($config['db_host'], $config['db_user'], $config['db_pass']) or error("Unable to connect to MySQL");
$selected = mysql_select_db($config['db_name'],$dbh) or error("Could not select database");

# get the location_id of our proxy; use 1 if none available
$result = mysql_fetch_array( mysql_query("SELECT  location_id FROM proxy_settings WHERE fqdn_proxy_hostname = '$hostname'") );
$location_id = $result['location_id'];
if ( $location_id == null ) {
      $location_id = 1;
}
#print $location_id;

# update no-auth files
updateFile($filename_ip, "SELECT sitename, description FROM noauth_rules WHERE type='IP' 
      AND (location_id = $location_id OR location_id = 1 OR location_id IS NULL) 
      AND (valid_until IS NULL OR valid_until > NOW()) ");

updateFile($filename_dn, "SELECT sitename, description FROM noauth_rules WHERE type='DN' 
      AND (location_id = $location_id OR location_id = 1 OR location_id IS NULL) 
      AND (valid_until IS NULL OR valid_until > NOW()) ");

mysql_close($dbh);

# Reload squid if no-auth rules have changed
if ($dirty_config == true) {
   exec("$squid_init_script status", $out, $retval);
   if ($retval == 0) {
      syslog ( LOG_WARNING, "No-auth lists were updated. Reloading Squid config..." );
      exec("$squid_init_script reload", $out, $retval);
   }
}



###############################
##### some functions

function stop($text, $code=0) {
   echo $text;
   exit($code);
}

function error($text) {
   stop($text, 1);
}

# write the result of the mysql-query to a file
function updateFile($filename, $query) {
   global $dirty_config;

   $file_md5_pre = md5_file($filename);

   $file = fopen($filename, 'w') or error("Can't open file $filename");

   $result = mysql_query($query);
   while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
      fwrite($file, $row{'sitename'} . "\n" );
      #echo $row{'sitename'}."\n";   # debug
   }

   fclose($file);

   if ( $file_md5_pre != md5_file($filename) ) {
      $dirty_config = true;
      syslog ( LOG_WARNING, "MD5 changed for file $filename - reloading squid config later" );
   }
}


?>
