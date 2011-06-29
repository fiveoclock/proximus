<?php
@include_once 'smarty/libs/Smarty.class.php';
error_reporting(E_ALL);
ini_set('display_errors', true);
session_start();

# global variables
$settings; $site; $log_id; $url;

# read config file, connect to mysql and retrieve settings from database
$config = parse_ini_file('/etc/proximus/proximus.conf');
db_connect();
getGlobalSettings();

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

      $data = array();
      $data['parent_id'] = $log_id;
      $data['url'] = $url;
      $data['row'] = $row;
      $data['settings'] = $settings;
      $_SESSION["id_$log_id"] = $data;

      header ("Location: " . $_SERVER['PHP_SELF'] . "?action=confirm");
   }
   elseif ( isset($_COOKIE['proximus']) && isset($_SESSION['parent_id']) ) {
      # if a valid cookie is present and session parent_id is set
      # save request as subsite entry
      updateLog($log_id, $_SESSION['parent_id']);
      setcookie ("proximus", "confirm", time() + $settings['dyn_rules_timeout2']  );
      #header("HTTP/1.1 301 Moved Permanently");
      header ("Location: $url");
   }
   else {
      # delete cookie and session
      setcookie ("proximus", "confirm", time()-3600 );
      session_destroy();
   }    

}
elseif ( isset($_POST['parent_id']) && isset($_POST['confirm']) && isset($_POST['url']) && isset($_SESSION['userid']) ) {
   # user has confirmed the request; updating log, setting cookie
   # and redirecting to original url
   $url = $_POST['url'];
   $parent_id = addslashes($_POST['parent_id']);
   $user_id = $_SESSION['userid'];
   
   # check if request is faked
   $result = mysql_query("SELECT id FROM logs WHERE id = $parent_id AND user_id = ".$user_id);
   if ( mysql_num_rows($result) < 1 ) {
      # looks like request was faked
      exit;
   }
   #print mysql_error();

   updateLog($parent_id, null);
   $_SESSION["id_$parent_id"] = null;
   setcookie ("proximus", "confirm", time() + $settings['dyn_rules_timeout1'] );
   #header("HTTP/1.1 301 Moved Permanently");
   header ("Location: ".$url);
}
elseif ( isset($_GET['action'] ) ) {
   global $site;
   $action = $_GET["action"];

   if ($action == "confirm" ) {
      $cur_id = $_SESSION['parent_id'];
      $data = $_SESSION["id_$cur_id"];

      $body = "
      <center>
      <dl>
         <dt>You were trying to access the following site: </dt>
         <dt><a href=\"".$data['url']."\">". $data['url'] ."</a></dd>
         <br><br>
         <dd>Username: ".$data['row']['username']."</dd>
         <dd>Site: ".    $data['row']['sitename']."</dd>
         <dd>Protocol: ".$data['row']['protocol']."</dd>
         <dd>Log ID: ".  $data['parent_id'] . "
          /  Client: ".  $data['row']['ipaddress']."</dd>
      </dl>
      <br> " . '

      <dl><dt>Click the confirm button below to whitelist this site</dt></dl><br>

      <form action="' . $_SERVER['PHP_SELF'] .'" method="post">
         <input type="hidden" name="url" value="' . $data['url'] . '">
         <input type="hidden" name="parent_id" value="' . $cur_id . '">
         <input type="submit" name="confirm" value="Confirm" >
      </form>
      <center> ';

      $smarty = setupSmarty("ProXimus - Confirmation", "User confirmation required", $body);
      $smarty->display('default.tpl'); 
   }


   if ($action == "DENY" ) {
     $site = $_GET["site"];
     $body = "
      <center>
      <dl>
         <dt>
         Access to the site you requested is denied due to User-Policy restrictions. <br><br> 
         Site: $site <br><br><br>
         If you need access to this site for good reasons please contact your IT Administrator.
         </dt>
      </dl>
      </center>
      ";
      $smarty = setupSmarty("ProXimus - Access denied", "Site blocked by policy", $body);
      $smarty->display('default.tpl'); 
   }
   

}
else {
   $body = "
   <dl>
      <dt>
      Choose from the menu above.
      </dt>
   </dl>
   ";

   $smarty = setupSmarty("ProXimus", "Start", $body);
   $smarty->display('default.tpl');
}



/////////////////
// functions

function db_connect() {
   global $config;
   $dbh = mysql_connect($config['db_host'], $config['db_user'], $config['db_pass']) or die("Unable to connect to MySQL");
   mysql_select_db($config['db_name'],$dbh) or die("Could not select database");
}

function setupSmarty($title="ProXimus", $subject="", $body="") {
   global $settings;
   $smarty = new Smarty();
   $smarty->template_dir = './templates/';
   $smarty->compile_dir = './templates/compile/';

   $smarty->assign('title_text', $title);
   $smarty->assign('subject', $subject);
   $smarty->assign('body_html', $body);
   $smarty->assign('settings', $settings);
   return $smarty;
}

function getRequest() {
   if ( isset($_GET["site"]) && isset($_GET["id"]) && isset($_GET["url"]) ) {
      # check if parameters are set
      
      global $site, $log_id, $url;
      $site = $_GET["site"];
      $log_id = addslashes($_GET["id"]);
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

function getGlobalSettings() {
   global $settings;
   $result = mysql_query("SELECT name, value FROM global_settings");
   while ($row = mysql_fetch_assoc($result)) {
      $settings[ $row['name'] ] = $row['value'];
   }
}

?>

