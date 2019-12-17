% rebase('base.tpl', subtitle='Network Map')
<script
  src="https://code.jquery.com/jquery-3.4.1.min.js"
  integrity="sha256-CSXorXvZcTkaix6Yvo6HppcZGetbYMGWSFlBw8HfCJo="
  crossorigin="anonymous"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis-network.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.11/lodash.min.js"></script>
<link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis-network.min.css" />
<input class="pure-button" type="button" id="bt_refresh" value="Refresh"><br>
<div id="zigatenetworkmap" style="height:500px"></div>

<script>
$( document ).ready(function() {
	let dataSetOptions = { queue: true };
	_nodesDataset = new vis.DataSet([], dataSetOptions);
    _edgesDataset = new vis.DataSet([], dataSetOptions);
 	_networkOptions = {
 	          physics: {
 	            enabled: true
 	            ,repulsion: { springLength: 100 }
 	            ,barnesHut: { springLength: 100, gravitationalConstant: -30000 }
 	            ,solver: 'barnesHut'
 	          },
 	          autoResize: true,
 	          width: '100%',
 	          height: '100%',
 	          nodes: {
 	            shape: 'box'
 	            ,mass: 1.2
 	          },
 	          edges: {
 	            smooth: false
 	            ,scaling: { label: false, max: 10 }
 	            ,font: {align: 'top', vadjust: 2, size: 12}
 	          },
 	          layout: {
 	            randomSeed: 0,
 	            hierarchical: {
 	              enabled: false,
 	              sortMethod: 'directed'
 	            }
 	          },
 	          interaction: {
 	            hover: true,
 	          }
 	        };
 	        
 	        _nodeCustomizations = {
 	          'zigate': {
 	            shape: 'ellipse'
 	            ,x: 0
 	            ,y: 0        	    	
 	          },
 	          'missing' : {
 	            color: { border: 'red', background:'#ffb3b3', hover: { border: 'red', background:'#ffeeee' } , highlight: { border: 'red', background:'#ffeeee' }}
 	            ,physics: false
 	            ,x: -1000
 	            ,y: -1000           
 	          }
 	        };

 	        _edgeCustomizations = {
 	          'duplicated': {
 	            font : {align : 'bottom', vadjust:-2}     
 	            ,color : {color : 'gray', opacity: 0.3 }    	
 	          }
 	        };
 	
 	
    let container = document.getElementById('zigatenetworkmap');
    let data = {
      nodes: _nodesDataset,
      edges: _edgesDataset
    }
    _networkGraph = new vis.Network(container, data, _networkOptions);
    refreshData();  
});
      function refreshData(force=false) {
        _edgesDataset.clear();
        _nodesDataset.clear();
        
        let zigateDevicesStates = new Array();
        let addrToIeeeTable = new Array();
        
        $.getJSON('{{get_url('api_devices')}}', function(devices){
        	devices['devices'].forEach(function (entity) {
                let entityIeee = entity.info.ieee;
                let entityAddr = entity.info.addr;
                let entityMissing = entity.info.missing;
                
                addrToIeeeTable[entityAddr] = entityIeee;
                
                //Use ieee as node Id
                let node = {
                  id: entityIeee 
                  //, label: entity.entity_id
                  , label: entity.friendly_name
                  , title: '<strong>' + entity.friendly_name
                    + '</strong><br>IEEE : ' + entity.info.ieee
                    + '</strong><br>ADDR : ' + entity.info.addr
                    + '</strong><br>LQI : ' + (entity.info.lqi | 0)
                };

                if (entityAddr === '0000') {
                	 node = _.merge(node, _nodeCustomizations.zigate);
                }

                if (entityMissing === true || entity.state == 'unknown') {
                	 node = _.merge(node, _nodeCustomizations.missing);
                }

                if(typeof(this._nodeCustomizations[entityIeee]) === 'object'){
                  node = _.merge(node, _nodeCustomizations[entityIeee]);
                }
        
                _nodesDataset.add(node);
              });     
        });

        var duplicates = [];
        $.getJSON('{{get_url('api_network_table')}}',{'force':force}, function(data){
        	var network_table = data['network_table'];
	        var links = network_table.sort((a,b) => a[2]>b[2] ? -1 : 0);
	        links.forEach(function (link) {
	          //count duplicate links to find duplicated edges
	          var duplicatesKey = [link[0], link[1]].sort().join()
	          if(typeof(duplicates[duplicatesKey]) === 'undefined')
	            duplicates[duplicatesKey] = 1;
	          else 
	            duplicates[duplicatesKey]++;
	
	          if (link[0] != link[1]) {
	            let edge = {
	              from: addrToIeeeTable[link[0]] 
	              ,to: addrToIeeeTable[link[1]]
	              ,value: link[2]
	              ,title: 'lqi: ' + link[2].toString()
	              ,label: link[2].toString()
	            };
	            if(duplicates[duplicatesKey] > 1){
	              edge = _.merge(edge, _edgeCustomizations['duplicated']);
	            }
	
	            //specific edge customizations
	            //id format should be ieee_ieee in panel.config.edges
	            let customizationEdgeId = edge.from + '_' + edge.to;
	            if(typeof(_edgeCustomizations[customizationEdgeId] !== 'undefined')){
	              edge = _.merge(edge, _edgeCustomizations[customizationEdgeId]);
	            }
	            
	            _edgesDataset.add(edge);
	          }
	        });
	
	        _edgesDataset.flush(); 
	        _nodesDataset.flush();
	        _networkGraph.stabilize();
        });
        
      }
      $('#bt_refresh').click(function() {
      	refreshData(true);
      });
      
 
  </script>
