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
from zigate import version as zigate_version
from zigate.core import DeviceEncoder
from zigate.const import ADMINPANEL_PORT, ADMINPANEL_HOST
import time


bottle.TEMPLATE_PATH.insert(0, os.path.join(os.path.dirname(__file__), 'views/'))


def start_adminpanel(zigate_instance, host=ADMINPANEL_HOST, port=ADMINPANEL_PORT, mount=None, prefix=None,
                     autostart=True, daemon=True, quiet=True, debug=False):
    '''
    mount: url prefix used to mount bottle application
    prefix: special prefix added when using get_url in template, eg proxy.php
    '''
    app = bottle.Bottle()
    app.install(bottle.JSONPlugin(json_dumps=lambda s: dumps(s, cls=DeviceEncoder)))

    def get_url(routename, **kwargs):
        '''
        customized get_url to allow additional prefix args
        '''
        redirect = kwargs.pop('redirect', False)
        scriptname = bottle.request.environ.get('SCRIPT_NAME', '').strip('/') + '/'
        location = app.router.build(routename, **kwargs).lstrip('/')
        url = bottle.urljoin(bottle.urljoin('/', scriptname), location)
        if prefix and not redirect:
            url = prefix + '?' + bottle.urlencode({'q': url})
        append = '?'
        if '?' in url:
            append = '&'
        url += '{}_={}'.format(append, time.time())
        return url

    def redirect(routename, **kwargs):
        '''
        convenient function to redirect using routename instead of url
        '''
        return bottle.redirect(get_url(routename, redirect=True, **kwargs))

    bottle.BaseTemplate.defaults['get_url'] = get_url
    bottle.BaseTemplate.defaults['zigate'] = zigate_instance
    app.zigate = zigate_instance

    @app.route('/', name='index')
    @bottle.view('index')
    def index():
        connected = zigate_instance.connection and zigate_instance.connection.is_connected()

        grouped_devices = {}
        processed = []

        def add_device_to_group(group, addr, endpoint=''):
            name = 'Missing'
            last_seen = ''
            if addr == zigate_instance.addr:
                name = 'ZiGate'
            zdev = zigate_instance.get_device_from_addr(addr)
            if zdev:
                name = str(zdev)
                last_seen = zdev.info.get('last_seen', '')
            else:
                name = '{} ({})'.format(name, addr)
            group.append({'addr': addr, 'endpoint': endpoint, 'name': name, 'last_seen': last_seen})

        for group, group_devices in zigate_instance.groups.items():
            grouped_devices[group] = []
            for device in group_devices:
                addr = device[0]
                endpoint = device[1]
                processed.append(addr)
                add_device_to_group(grouped_devices[group], addr, endpoint)

        grouped_devices[''] = []
        for device in zigate_instance.devices:
            if device.addr not in processed:
                add_device_to_group(grouped_devices[''], device.addr)

        port = zigate_instance._port or 'auto'
        if hasattr(zigate_instance, '_host'):
            port = '{}:{}'.format(zigate_instance._host, port)

        return {
            'libversion': zigate_version.__version__,
            'port': port,
            'connected': connected,
            'version': zigate_instance.get_version_text(),
            'model': zigate_instance.model,
            'groups': zigate_instance.groups,
            'grouped_devices': grouped_devices,
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
            return redirect('index')
        return {'device': device}

    @app.route('/raw_command', name='raw_command', method=['POST'])
    def raw_command():
        cmd = bottle.request.forms.get('cmd')
        data = bottle.request.forms.get('data')
        cmd = int(cmd, 16)
        zigate_instance.send_data(cmd, data)
        return redirect('index')

    @app.route('/api/permit_join', name='api_permit_join')
    def permit_join():
        zigate_instance.permit_join()
        return redirect('index')
    
    @app.route('/api/reset', name='api_reset')
    def reset():
        zigate_instance.reset()
        return redirect('index')

    @app.route('/api/led', name='api_led')
    def set_led():
        on = bottle.request.query.get('on', 'true') == 'true'
        zigate_instance.set_led(on)
        return redirect('index')

    @app.route('/api/discover/<addr>', name='api_discover')
    def api_discover(addr):
        zigate_instance.discover_device(addr, True)
        return redirect('device', addr=addr)

    @app.route('/api/refresh/<addr>', name='api_refresh')
    def api_refresh(addr):
        zigate_instance.refresh_device(addr)
        return redirect('device', addr=addr)

    @app.route('/api/remove/<addr>', name='api_remove')
    def api_remove(addr):
        force = bottle.request.query.get('force', 'false') == 'true'
        zigate_instance.remove_device(addr, force)
        return redirect('index')

    @app.route('/device/<addr>/save', name='device_save', method=['GET', 'POST'])
    def device_save(addr):
        device = zigate_instance.get_device_from_addr(addr)
        if not device:
            return redirect('index')
        device.name = bottle.request.forms.name
        return redirect('device', addr=addr)

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

    kwargs = {'host': host, 'port': port,
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
