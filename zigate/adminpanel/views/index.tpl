% rebase('base.tpl')
<ul>
	<li>Lib version : {{libversion}}</li>
	<li>Port : {{port}}</li>
	<li>Connected : {{connected}}</li>
	<li>Firmware version : {{version}}</li>
</ul>

<h2>Devices :</h2>
<ul>
  % for device in devices:
    <li>{{device}}</li>
  % end
</ul>

<h2>Groups :</h2>
{{groups}}

<h2>Actions :</h2>
<a href="/api/permit_join">Permit Join</a>