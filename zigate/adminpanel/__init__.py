#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

import os
import threading
import bottle
from json import dumps
from zigate.core import DeviceEncoder
from zigate.const import ADMINPANEL_PORT


bottle.TEMPLATE_PATH.insert(0, os.path.join(os.path.dirname(__file__), 'views/'))


def start_adminpanel(zigate_instance, port=ADMINPANEL_PORT, mount=None, prefix=None,
                     autostart=True, daemon=True, quiet=True, debug=False):
    '''
    mount: url prefix used to mount bottle application
    prefix: special prefix added when using get_url in template
    '''
    app = bottle.Bottle()
    app.install(bottle.JSONPlugin(json_dumps=lambda s: dumps(s, cls=DeviceEncoder)))

    def get_url(routename, **kargs):
        '''
        customized get_url to allow additionnal prefix args
        '''
        scriptname = bottle.request.environ.get('SCRIPT_NAME', '').strip('/') + '/'
        location = app.router.build(routename, **kargs).lstrip('/')
        url = bottle.urljoin(bottle.urljoin('/', scriptname), location)
        if prefix:
            url = prefix + url
        return url

    bottle.BaseTemplate.defaults['get_url'] = get_url
    bottle.BaseTemplate.defaults['zigate'] = zigate_instance
    app.zigate = zigate_instance

    @app.route('/', name='index')
    @bottle.view('index')
    def index():
        from zigate import version
        connected = zigate_instance.connection and zigate_instance.connection.is_connected()
        return {'port': zigate_instance._port or 'auto',
                'libversion': version.__version__,
                'version': zigate_instance.get_version_text(),
                'connected': connected,
                'devices': zigate_instance.devices,
                'groups': zigate_instance.groups,
                'model': zigate_instance.model
                }

    @app.route('/networkmap', name='networkmap')
    @bottle.view('networkmap')
    def networkmap():
        return

    @app.route('/device/<addr>', name='device')
    @bottle.view('device')
    def device(addr):
        device = zigate_instance.get_device_from_addr(addr)
        if not device:
            return bottle.redirect('/')
        return {'device': device}

    @app.route('/api/permit_join', name='api_permit_join')
    def permit_join():
        zigate_instance.permit_join()
        return bottle.redirect('/')

    @app.route('/api/discover/<addr>', name='api_discover')
    def api_discover(addr):
        zigate_instance.discover_device(addr, True)
        return bottle.redirect(get_url('device', addr=addr))

    @app.route('/api/refresh/<addr>', name='api_refresh')
    def api_refresh(addr):
        zigate_instance.refresh_device(addr)
        return bottle.redirect(get_url('device', addr=addr))

    @app.route('/api/remove/<addr>', name='api_remove')
    def api_remove(addr):
        force = bottle.request.query.get('force', 'false') == 'true'
        zigate_instance.remove_device(addr, force)
        return bottle.redirect('/')

    @app.route('/api/devices', name='api_devices')
    def devices():
        devices = [{'info': {'addr': zigate_instance.addr,
                             'ieee': zigate_instance.ieee
                             },
                    'friendly_name': 'ZiGate'
                    }]
        for d in zigate_instance.devices:
            device = d.to_json()
            device['friendly_name'] = str(d)
            devices.append(device)
        return {'devices': devices}

    @app.route('/api/network_table', name='api_network_table')
    def network_table():
        force = bottle.request.query.get('force', 'false') == 'true'
        return {'network_table': zigate_instance.build_neighbours_table(force)}

    kwargs = {'host': '0.0.0.0', 'port': port,
              'quiet': quiet, 'debug': debug}

    if autostart:
        r_app = app
        if mount:
            root_app = bottle.Bottle()
            root_app.mount(mount, app)
            r_app = root_app
        if daemon:
            t = threading.Thread(target=r_app.run,
                                 kwargs=kwargs,
                                 daemon=True)
            t.start()
        else:
            r_app.run(**kwargs)
    return app


if __name__ == '__main__':
    import zigate
    zigate_instance = zigate.connect('fake')
    start_adminpanel(zigate_instance, daemon=False, quiet=False, debug=True)
