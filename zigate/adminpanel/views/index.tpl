% rebase('base.tpl')
<div style="display: inline-block; vertical-align: top;">
	<h3>ZiGate</h3>
	<table class="pure-table pure-table-bordered">
		<thead>
			<tr>
				<th>Attribute</th>
				<th>Value</th>
			<tr>
		</thead>
		<tbody>
			<tr>
				<td>Lib version</td>
				<td>{{libversion}}</td>
			</tr>
			<tr>
				<td>Port</td>
				<td>{{port}}</td>
			</tr>
			<tr>
				<td>Connected</td>
				<td>{{connected}}</td>
			</tr>
			<tr>
				<td>Firmware version</td>
				<td>{{version}}</td>
			</tr>
			<tr>
				<td>Model</td>
				<td>{{model}}</td>
			</tr>
		</tbody>
	</table>
</div>

<div style="display: inline-block; vertical-align: top;">
	<h3>Actions</h3>
	<a class="pure-button" href="{{get_url('api_permit_join')}}">Permit Join</a>
	<a class="pure-button" href="{{get_url('api_reset')}}">Reset</a>
	<a class="pure-button" href="{{get_url('api_led', on='true')}}">Led ON</a>
	<a class="pure-button" href="{{get_url('api_led', on='false')}}">Led OFF</a>
	<form method="post" action="{{get_url('raw_command')}}">
	Raw command :
	<label for="cmd">Cmd : </label><input type="text" name="cmd" placeholder="0x0000">
	<label for="data">Data : </label><input type="text" name="data" placeholder="optionnal binary payload">
	<input type="submit" name="Send">
	</form>
</div>

<br>

<div style="display: inline-block; vertical-align: top;">
	<h3>Devices</h3>
	<table class="pure-table pure-table-bordered">
		<thead>
			<tr>
				<th>Group</th>
				<th>Endpoint</th>
				<th>Addr</th>
				<th>Device</th>
				<th>Last Seen</th>
			<tr>
		</thead>
		<tbody>
		% for group, group_devices in grouped_devices.items():
			% for i, device in enumerate(group_devices):
			<tr>
				% if i == 0:
				<td rowspan="{{len(group_devices)}}">{{group}}</td>
				% end
				% if group or i == 0:
				<td rowspan="{{1 if group else len(group_devices)}}">{{device['endpoint']}}</td>
				% end
				<td>{{device['addr']}}</td>
				<td><a href="{{get_url('device', addr=device['addr'])}}">{{device['name']}}</a></td>
				<td>{{device['last_seen']}}</td>
			</tr>
			%end
		% end
		</tbody>
	</table>
</div>

<div style="display: inline-block; vertical-align: top;">
	<h3>Groups</h3>
	<table class="pure-table pure-table-bordered">
		<thead>
			<tr>
				<th>Group</th>
				<th>Devices</th>
			<tr>
		</thead>
		<tbody>
		% for group, group_devices in groups.items():
			<tr>
				<td>{{group}}</td>
				<td>{{group_devices}}</td>
			</tr>
		% end
		</tbody>
	</table>
</div>
