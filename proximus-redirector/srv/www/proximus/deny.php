<?php

#define('SMARTY_DIR', 'smarty/' );
#require_once('Smarty.class.php');
@include_once 'smarty/libs/Smarty.class.php';

session_start();

$site = $_SESSION['site'];

$text .= "<dl>";
$text .= "<dt>";
$text .= "Access to the site you requested is denied due to User-Policy restrictions. <br><br> Site: $site <br><br><br>If you need access to this site for good reasons please contact your IT Administrator.";
$text .= "</dt>";
$text .= "</dl>";

$smarty = new Smarty();
$smarty->template_dir = './templates/';
$smarty->compile_dir = './templates/compile/';

$smarty->assign('title_text', 'ProXimus - Access denied');
$smarty->assign('title', 'Site blocked by policy');
$smarty->assign('body_html', $text);

$smarty->display('confirm.tpl');

?>
