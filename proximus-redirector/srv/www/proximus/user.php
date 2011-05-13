<?php
session_start();
# global variables
$dbh;

# read config file
$config = parse_ini_file('/etc/proximus/proximus.conf');

# connect to mysql
$dbh = mysql_connect($config['db_host'], $config['db_user'], $config['db_pass']) or die("Unable to connect to MySQL");
$selected = mysql_select_db($config['db_name'],$dbh) or die("Could not select database");

$site;
$log_id;
$url;

# show all sites accessed, show sites recently blocked, show 


if ( isset($_SESSION['userid']) ) {
   $data = $_SESSION;
   $result = mysql_query("SELECT sitename, ipaddress, protocol, hitcount FROM logs WHERE source != 'REDIRECT' AND user_id = ".$data['userid']);
   echo "<b>Sites you have visited: </b><br><br>";
   while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
      print "".$row{'sitename'}." ".$row{'protocol'}."<br>";
   }
   echo "<br><br>";

   $result = mysql_query("SELECT sitename, ipaddress, protocol, hitcount FROM logs WHERE source = 'REDIRECT' AND user_id = ".$data['userid']." ORDER BY id DESC LIMIT 10");
   echo mysql_error();
   echo "<b>Sites that have been blocked recently: </b><br><br>";
   while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
      print "".$row{'sitename'}." ".$row{'protocol'}."<br>";
   }
   echo "<br><br>";
}
else {
   # user is not logged in - show login box
   echo "please log in first..";
}


function printResult($arr, $head) {
   if ( is_array($head) ) {
      
}

function printResult($result) {
   while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
      print "".$row{'sitename'}." ".$row{'protocol'}."<br>";
   }
     
}

function updateLog($log_id, $parent_id) {
   if ( $parent_id != null ) {
      mysql_query("UPDATE logs SET source = 'USER', parent_id = '$parent_id' WHERE id = '$log_id'");
   }
   else {
      mysql_query("UPDATE logs SET source = 'USER' WHERE id = '$log_id'");
   }
}

mysql_close($dbh);
?>

