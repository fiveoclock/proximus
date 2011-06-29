<html>
<head>
<title>{$title_text|escape}</title>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" /><link rel="stylesheet" type="text/css" href="css/style.css" media="all" />
</head>
<body>
<div id="header">

<img id=logo src="images/logo.png">
<div id="title">
ProXimus
</div>

<div id="slogan">{$subject|escape}</div>
</div>

<div id="nav">
{if isset( $settings.login_url ) } 
   <a href="{$settings.login_url}">Login</a>
{/if}
<a href="#" onClick="history.go(-1);return false">Go back</a>
</div>


<div id="content">
<div id="maincontent">
<br>

{$body_html}

</div>
</div>

</body>
</html>

