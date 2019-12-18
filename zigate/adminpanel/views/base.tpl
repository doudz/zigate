<!doctype html>
<html>
	<head>
		<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
		<meta http-equiv="Pragma" content="no-cache" />
		<meta http-equiv="Expires" content="0" />
		<meta charset="utf-8">
		<meta name="viewport" content="width=device-width, initial-scale=1.0">
		<title>ZiGate Admin Panel</title>
		<link rel="stylesheet" href="https://unpkg.com/purecss@1.0.1/build/pure-min.css" integrity="sha384-oAOxQR6DkCoMliIh8yFnu25d7Eq/PHS21PClpwjOTeU2jRSq11vu66rf90/cZr47" crossorigin="anonymous">
	</head>
	<body style="margin:10px">
		<h1>ZiGate Admin Panel</h1>
		<div class="pure-menu pure-menu-horizontal">
			<ul class="pure-menu-list">
				<li class="pure-menu-item"><a class="pure-menu-link" href="{{get_url('index')}}">Index</a></li>
				<li class="pure-menu-item"><a class="pure-menu-link" href="{{get_url('networkmap')}}">Network Map</a></li>
			</ul>
		</div>
		<h2>{{get('subtitle', 'Index')}}</h2>
		{{!base}}
	</body>
</html>