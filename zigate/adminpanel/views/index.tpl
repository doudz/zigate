% rebase('base.tpl')
<ul>
	<li>Lib version : {{libversion}}</li>
	<li>Port : {{port}}</li>
	<li>Connected : {{connected}}</li>
	<li>Firmware version : {{version}}</li>
	<li>Model : {{model}}</li>
</ul>

<h2>Devices :</h2>
<table class="pure-table pure-table-bordered">
	<thead>
		<tr>
			<th>Device</th>
			<th>Last Seen</th>
		<tr>
	</thead>
	<tbody>
	  % for device in devices:
	  	<tr>
	    	<td><a href="{{get_url('device', addr=device.addr)}}">{{device}}</a></td>
	    	<td>{{device.info.get('last_seen')}}</td>
	    </tr>
	  % end
  	</tbody>
</table>

<h2>Groups :</h2>
{{groups}}

<h2>Actions :</h2>
<a class="pure-button" href="{{get_url('api_permit_join')}}">Permit Join</a>