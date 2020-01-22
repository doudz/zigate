% rebase('base.tpl', subtitle='Network Map')
<script src="https://unpkg.com/vis-network@7.1.0/standalone/umd/vis-network.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.15/lodash.min.js"></script>

<div id="zigatenetworkmap"
    style="display: inline-block; border: solid rgb(238, 244, 253); width: 65vw; min-width: 700px; min-height: 700px; height: 78vh;">
</div>
<div style="display: inline-block; border: solid #eef4fd; width: 525px; height: auto; vertical-align: top;">
    <div id="actions" style="padding: 4px">
        <input class="pure-button" type="button" id="bt_refresh" value="Refresh">
        <input class="pure-button" type="button" id="bt_force_refresh" value="Force Refresh">
    </div>
    <div id="config">
        <style>
            div.vis-configuration-wrapper {
                width: 525px;
            }
        </style>
    </div>
</div>

<script>
    $(document).ready(function () {
        _networkOptions = {
            physics: {
                enabled: true,
                stabilization: false,
                forceAtlas2Based: {
                    "springLength": 100,
                    "avoidOverlap": 1
                },
                solver: 'forceAtlas2Based'
            },
            autoResize: true,
            width: '100%',
            height: '100%',
            nodes: {
                shape: 'box',
                mass: 1.2
            },
            edges: {
                smooth: false,
                scaling: { label: false, max: 10 },
                font: { align: 'top', vadjust: 2, size: 12 }
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
            },
            configure: {
                filter: function (option, path) {
                    if (path.indexOf('physics') !== -1) {
                        return true;
                    }
                    if (path.indexOf('smooth') !== -1 || option === 'smooth') {
                        return true;
                    }
                    return false;
                },
                container: document.getElementById('config')
            }
        };

        _nodeCustomizations = {
            'zigate': {
                shape: 'ellipse'
                , x: 0
                , y: 0
            },
            'missing': {
                color: { border: 'red', background: '#ffb3b3', hover: { border: 'red', background: '#ffeeee' }, highlight: { border: 'red', background: '#ffeeee' } }
                , physics: false
                , x: -1000
                , y: -1000
            }
        };

        _edgeCustomizations = {
            'duplicated': {
                font: { align: 'bottom', vadjust: -2 }
                , color: { color: 'gray', opacity: 0.3 }
            }
        };


        let dataSetOptions = { queue: true };
        _nodesDataset = new vis.DataSet([], dataSetOptions);
        _edgesDataset = new vis.DataSet([], dataSetOptions);

        let data = {
            nodes: _nodesDataset,
            edges: _edgesDataset
        }

        let container = document.getElementById('zigatenetworkmap');
        _networkGraph = new vis.Network(container, data, _networkOptions);
        refreshData();
    });

    function refreshData(force = false) {
        let zigateDevicesStates = new Array();
        let addrToIeeeTable = new Array();

        $.getJSON('{{get_url('api_devices')}}', function (devices) {
            _nodesDataset.clear();
            _edgesDataset.clear();

            devices['devices'].forEach(function (entity) {
                let entityIeee = entity.info.ieee;
                let entityAddr = entity.info.addr;
                let entityMissing = entity.info.missing;

                addrToIeeeTable[entityAddr] = entityIeee;

                //Use ieee as node Id
                let node = {
                    id: entityIeee
                    , label: entity.friendly_name.replace(" (", "\n<i>").replace(") ", "</i>\n")
                    , font: { multi: "html" }
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

                if (typeof (this._nodeCustomizations[entityIeee]) === 'object') {
                    node = _.merge(node, _nodeCustomizations[entityIeee]);
                }

                _nodesDataset.add(node);
            });

            _nodesDataset.flush();

            var duplicates = [];
            $.getJSON('{{get_url('api_network_table')}}', { 'force': force }, function (data) {
                var network_table = data['network_table'];
                var links = network_table.sort((a, b) => a[2] > b[2] ? -1 : 0);
                links.forEach(function (link) {
                    //count duplicate links to find duplicated edges
                    var duplicatesKey = [link[0], link[1]].sort().join()
                    if (typeof (duplicates[duplicatesKey]) === 'undefined')
                        duplicates[duplicatesKey] = 1;
                    else
                        duplicates[duplicatesKey]++;

                    if (link[0] != link[1]) {
                        let edge = {
                            from: addrToIeeeTable[link[0]]
                            , to: addrToIeeeTable[link[1]]
                            , value: link[2]
                            , title: 'lqi: ' + link[2].toString()
                            , label: link[2].toString()
                        };
                        if (duplicates[duplicatesKey] > 1) {
                            edge = _.merge(edge, _edgeCustomizations['duplicated']);
                        }

                        //specific edge customizations
                        //id format should be ieee_ieee in panel.config.edges
                        let customizationEdgeId = edge.from + '_' + edge.to;
                        if (typeof (_edgeCustomizations[customizationEdgeId] !== 'undefined')) {
                            edge = _.merge(edge, _edgeCustomizations[customizationEdgeId]);
                        }

                        _edgesDataset.add(edge);
                    }
                });

                _edgesDataset.flush();

                _networkGraph.stabilize();
            });
        });
    }
    $('#bt_refresh').click(function () {
        refreshData(false);
    });

    $('#bt_force_refresh').click(function () {
        refreshData(true);
    });
</script>
