<?php

#define('SMARTY_DIR', 'smarty/' );
#require_once('Smarty.class.php');
@include_once 'smarty/libs/Smarty.class.php';

session_start();


$cur_id = $_SESSION['parent_id'];
$data = $_SESSION["id_$cur_id"];

$text .= "You were trying to access the following site: <br><br>";

$text .= "Log id: ".  $data['parent_id']."<br>";
$text .= "URL: ".     $data['url']."<br>";
$text .= "Site: ".    $data['row']['sitename']."; ";
$text .= "Protocol: ".$data['row']['protocol']."<br>";
$text .= "User: ".    $data['row']['username']."; ";
$text .= "Client: ".  $data['row']['ipaddress']."<br><br>";

$text .= "Please click the confirm button if you need acccess to this site.";

$text .= '<form action="proximus.php" method="post">';
$text .= '<input type="hidden" name="url" value="'.$data['url']. '">';
$text .= '<input type="hidden" name="parent_id" value="'.$cur_id. '">';
$text .= '<input type="submit" name="confirm" value="Confirm" >';
$text .= '</form>';


$smarty = new Smarty();
$smarty->template_dir = './templates/';
$smarty->compile_dir = './templates/compile/';
 
$smarty->assign('title_text', 'TITLE: This is the Smarty basic example ...');
$smarty->assign('body_html', $text);
 
$smarty->display('confirm.tpl');

?>
