<?php
//error_reporting(E_ALL);
//ini_set('display_errors', true);

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

if ( getRequest() )  {
   # redirected by proximus - no log exists
   # case 1: no cookie -> redirect to confirmation page
   # case 2: cookie present -> add subsite entry

   # check if request is faked
   $result = mysql_query("SELECT sitename, ipaddress, protocol, hitcount, users.id AS userid, username, realname FROM logs, users WHERE user_id = users.id AND logs.id = $log_id");
   $row = mysql_fetch_assoc($result);
   if ($site != $row['sitename']) {
      setcookie ("proximus", "confirm", time()-3600 );
      # "looks like the request was faked"
      exit;
   }
  
   if ( !isset($_COOKIE['proximus']) ) {
      # if no cookie is present store the request details into the session and
      # redirect the user to the confirmation site

      # start new session
      #session_destroy();
      #session_start();

      $_SESSION['parent_id'] = $log_id;
      $_SESSION['url'] = $url;
      $_SESSION['userid'] = $row['userid'];
      $_SESSION['username'] = $row['username'];
      $_SESSION['realname'] = $row['realname'];

      $x = array();
      $x['parent_id'] = $log_id;
      $x['url'] = $url;
      $x['row'] = $row;
      $_SESSION["id_$log_id"] = $x;

      header ("Location: confirm.php");
   }
   elseif ( isset($_COOKIE['proximus']) && isset($_SESSION['parent_id']) ) {
      # if a valid cookie is present and session parent_id is set
      # save request as subsite entry
      updateLog($log_id, $_SESSION['parent_id']);
      setcookie ("proximus", "confirm", time()+4 );
      #header("HTTP/1.1 301 Moved Permanently");
      header ("Location: $url");
   }
   else {
      # delete cookie and session
      setcookie ("proximus", "confirm", time()-3600 );
      session_destroy();
   }    

   /*
   $result = mysql_query("SELECT username, id FROM users limit 10");
   while ($row = mysql_fetch_array($result,MYSQL_ASSOC)) {
      print "ID:".$row{'id'}." Name:".$row{'username'}."<br>";
   }
   # get site:%s/id:%s/url:%s        
   */
}
elseif ( isset($_POST['parent_id']) && isset($_POST['confirm']) && isset($_POST['url']) && isset($_SESSION['userid']) ) {
   # user has confirmed the request; updating log, setting cookie
   # and redirecting to original url
   $url = $_POST['url'];
   $parent_id = $_POST['parent_id'];
   $data = $_SESSION;
   
   # check if request is faked
   $result = mysql_query("SELECT id FROM logs WHERE id = $parent_id AND user_id = ".$_SESSION['userid']);
   if ( mysql_num_rows($result) < 1 ) {
      # looks like request was faked
      exit;
   }
   #print mysql_error();

   updateLog($parent_id, null);
   $_SESSION["id_$parent_id"] = null;
   setcookie ("proximus", "confirm", time()+10 );
   #header("HTTP/1.1 301 Moved Permanently");
   header ("Location: ".$url);
}
elseif ( isset($_GET['action'] ) ) {
   global $site;
   $site = $_GET["site"];
   $action = $_GET["action"];

   if ($action == "DENY" ) {
      $_SESSION['site'] = $site;

      header ("Location: deny.php");
   }
}


function getRequest() {
   if ( isset($_GET["site"]) && isset($_GET["id"]) && isset($_GET["url"]) ) {
      # todo .. strip off bad things..
      # todo ... decode base64
      # check if parameters are set
      
      global $site, $log_id, $url;
      $site = $_GET["site"];
      $log_id = $_GET["id"];
      # decode url
      $url = base64_decode($_GET["url"]);
      return true;
   }
   else {
      return false;
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

