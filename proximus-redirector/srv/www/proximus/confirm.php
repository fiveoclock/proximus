<?php

#define('SMARTY_DIR', 'smarty/' );
#require_once('Smarty.class.php');
@include_once 'smarty/libs/Smarty.class.php';

session_start();

$cur_id = $_SESSION['parent_id'];
$data = $_SESSION["id_$cur_id"];

$text = "
<dl>
   <dt>You were trying to access the following site: </dt>

   <dt><a href=\"".$data['url']."\">". $data['url'] ."</a></dd>
   <br><br>
   <dd>Username: ".$data['row']['username']."</dd>
   <dd>Site: ".    $data['row']['sitename']."</dd>
   <dd>Protocol: ".$data['row']['protocol']."</dd>
   <dd>Log id: ".  $data['parent_id'] . "
    /  Client: ".  $data['row']['ipaddress']."</dd>
</dl>
<br>
";

$text .= '
<dl><dt>Click the confirm button below to get acccess to this site</dt></dl><br>

<form action="proximus.php" method="post">
   <input type="hidden" name="url" value="' . $data['url'] . '">
   <input type="hidden" name="parent_id" value="' . $cur_id . '">
   <input type="submit" name="confirm" value="Confirm" >
</form>
';


$smarty = new Smarty();
$smarty->template_dir = './templates/';
$smarty->compile_dir = './templates/compile/';
 
$smarty->assign('settings', $data['settings']);
$smarty->assign('title_text', 'ProXimus - Confirmation');
$smarty->assign('subject', 'User confirmation required');
$smarty->assign('body_html', $text);
 
$smarty->display('default.tpl');

?>
