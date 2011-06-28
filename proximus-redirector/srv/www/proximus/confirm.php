<?php

#define('SMARTY_DIR', 'smarty/' );
#require_once('Smarty.class.php');
@include_once 'smarty/libs/Smarty.class.php';

session_start();


$cur_id = $_SESSION['parent_id'];
$data = $_SESSION["id_$cur_id"];

$text .= "<dl>";
$text .= "<dt>You were trying to access the following site: <br></dt>";

$text .= "<dt><a href=\"".     $data['url']."\">". $data['url'] ."</a></dd><br><br>";

$text .= "<dd>User: ".    $data['row']['username']."</dd>";
$text .= "<dd>Site: ".    $data['row']['sitename']."</dd>";
$text .= "<dd>Log id: ".  $data['parent_id']."</dd>";
$text .= "<dd>Protocol: ".$data['row']['protocol']."</dd>";
$text .= "<dd>Client: ".  $data['row']['ipaddress']."</dd>";
$text .= "</dl><br>";

$text .= "<dl><dt>Click the confirm button below to get acccess to this site</dt></dl><br>";

$text .= '<form action="proximus.php" method="post">';
$text .= '<input type="hidden" name="url" value="'.$data['url']. '">';
$text .= '<input type="hidden" name="parent_id" value="'.$cur_id. '">';
$text .= '<input type="submit" name="confirm" value="Confirm" >';
$text .= '</form>';


$smarty = new Smarty();
$smarty->template_dir = './templates/';
$smarty->compile_dir = './templates/compile/';
 
$smarty->assign('title_text', 'ProXimus - Confirmation');
$smarty->assign('title', 'User confirmation required');
$smarty->assign('body_html', $text);
 
$smarty->display('confirm.tpl');

?>
