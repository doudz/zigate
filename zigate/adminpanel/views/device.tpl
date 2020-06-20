% rebase('base.tpl', subtitle='Device : ' + str(device))

<a class="pure-button" href="{{get_url('device', addr=device.addr)}}">Reload page</a>
<a class="pure-button" href="{{get_url('api_discover', addr=device.addr)}}">Discover</a>
<a class="pure-button" href="{{get_url('api_refresh', addr=device.addr)}}">Refresh</a>
<a class="pure-button" href="{{get_url('api_remove', addr=device.addr)}}">Remove</a>
<a class="pure-button" href="{{get_url('api_remove', addr=device.addr, force='true')}}">Delete</a>
<h3>Info :</h3>
<form method="post" action="{{get_url('device_save', addr=device.addr)}}">
	<label>Name : <input type="text" name="name" value="{{device.name}}"/></label>
	<input type="submit" value="Save"/>
</form>
<table class="pure-table pure-table-bordered">
  % for k, v in device.info.items():
  	<tr>
    	<td>{{k}}</td>
    	<td>{{v}}</td>
    </tr>
  % end
</table>
<h3>Endpoints :</h3>
% for endpoint_id, endpoint in device.endpoints.items():
<ul>
	<li>Endpoint : {{endpoint_id}}</li>
	<li>Profile ID : {{endpoint.get('profile')}}</li>
	<li>Device ID : {{endpoint.get('device')}}</li>
	<li>In clusters : {{endpoint.get('in_clusters')}}</li>
	<li>Out clusters : {{endpoint.get('out_clusters')}}</li>
</ul>
<table class="pure-table pure-table-bordered">
	<thead>
		<tr>
			<th>Cluster ID</th>
			<th>Cluster</th>
			<th>Attributes</th>
		</tr>
	</thead>
	<tbody>
	  	% for cluster_id, cluster in endpoint.get('clusters', {}).items():
	  	<tr>
	    	<td>{{cluster_id}}</td>
	    	<td>{{cluster}}</td>
	    	<td>
	    	% for attributes in cluster.attributes.values():
	    	<ul>
	    		% for k, v in attributes.items():
	    			<li>{{k}} : {{v}}</li>
	    		% end
	    	</ul>
	    	% end
	    	</td>
	    </tr>
	    % end
	</tbody>
</table>
% end