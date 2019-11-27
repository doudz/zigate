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