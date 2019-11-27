% rebase('base.tpl', subtitle='Network Map')
<script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis-network.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.11/lodash.min.js"></script>
<link rel="stylesheet" type="text/css" href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis-network.min.css" />
<div id="zigatenetworkmap"></div>

<script>
(function() {
	let dataSetOptions = { queue: true };
	_nodesDataset = new vis.DataSet([], dataSetOptions);
    _edgesDataset = new vis.DataSet([], dataSetOptions);
 	initNetworkOptions();
    initNetworkGraph();   
    refreshData();  
})();
      function initNetworkOptions(){
      	
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

      }

      function initNetworkGraph() {
        let container = document.getElementById('zigatenetworkmap');
        let data = {
          nodes: this._nodesDataset,
          edges: this._edgesDataset
        }
        _networkGraph = new vis.Network(container, data, this._networkOptions);
      }

      function refreshData() {
        this._edgesDataset.clear();
        this._nodesDataset.clear();

        let myzigate = this.hass.states['zigate.zigate'];
        let zigateDevicesStates = new Array();
        let addrToIeeeTable = new Array();

        for (let state in this.hass.states) {
          if (state.indexOf('zigate.') === 0)
            zigateDevicesStates.push(this.hass.states[state]); 
        }        

        zigateDevicesStates.forEach(function (entity) {
          let entityIeee = entity.attributes.ieee;
          let entityAddr = entity.attributes.addr;
          let entityMissing = entity.attributes.missing;
          
          addrToIeeeTable[entityAddr] = entityIeee;
          
          //Use ieee as node Id
          let node = {
            id: entityIeee 
            //, label: entity.entity_id
            , label: entity.attributes.friendly_name
            , title: '<strong>' + entity.attributes.friendly_name
              + '</strong><br>IEEE : ' + entity.attributes.ieee
              + '</strong><br>ADDR : ' + entity.attributes.addr
              + '</strong><br>LQI : ' + (entity.attributes.lqi | 0)
          };

          if (entityAddr === '0000') {
          	 node = _.merge(node, this._nodeCustomizations.zigate);
          }

          if (entityMissing === true || entity.state == 'unknown') {
          	 node = _.merge(node, this._nodeCustomizations.missing);
          }

          if(typeof(this._nodeCustomizations[entityIeee]) === 'object'){
            node = _.merge(node, this._nodeCustomizations[entityIeee]);
          }
  
          this._nodesDataset.add(node);
        }.bind(this));       

        var duplicates = [];
        var links = myzigate.attributes.network_table.sort((a,b) => a[2]>b[2] ? -1 : 0);
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
              edge = _.merge(edge, this._edgeCustomizations['duplicated']);
            }

            //specific edge customizations
            //id format should be ieee_ieee in panel.config.edges
            let customizationEdgeId = edge.from + '_' + edge.to;
            if(typeof(this._edgeCustomizations[customizationEdgeId] !== 'undefined')){
              edge = _.merge(edge, this._edgeCustomizations[customizationEdgeId]);
            }
            
            this._edgesDataset.add(edge);
          }
        }.bind(this));

        this._edgesDataset.flush(); 
        this._nodesDataset.flush();
        this._networkGraph.stabilize();     
      }
  </script>
