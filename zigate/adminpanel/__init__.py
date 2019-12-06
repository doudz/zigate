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
# from bottle import Bottle, route, view, template, redirect, TEMPLATE_PATH  # noqa

ADMINPANEL_PORT = 9998
bottle.TEMPLATE_PATH.insert(0, os.path.join(os.path.dirname(__file__), 'views/'))


def start_adminpanel(zigate_instance, port=ADMINPANEL_PORT, autostart=True, daemon=True, quiet=True, debug=False):
    app = bottle.Bottle()
    app.install(bottle.JSONPlugin(json_dumps=lambda s: dumps(s, cls=DeviceEncoder)))
    bottle.BaseTemplate.defaults['get_url'] = app.get_url
    bottle.BaseTemplate.defaults['zigate'] = zigate_instance
    app.zigate = zigate_instance

    @app.route('/')
    @bottle.view('index')
    def index():
        from zigate import version
        connected = zigate_instance.connection and zigate_instance.connection.is_connected()
        return {'port': zigate_instance._port or 'auto',
                'libversion': version.__version__,
                'version': zigate_instance.get_version_text(),
                'connected': connected,
                'devices': zigate_instance.devices,
                'groups': zigate_instance.groups
                }

    @app.route('/networkmap')
    @bottle.view('networkmap')
    def networkmap():
        return

    @app.route('/api/permit_join')
    def permit_join():
        zigate_instance.permit_join()
        bottle.redirect('/')

    kwargs = {'host': '0.0.0.0', 'port': port,
              'quiet': quiet, 'debug': debug}

    @app.route('/api/devices')
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

    @app.route('/api/network_table')
    def network_table():
        return {'network_table': zigate_instance.build_neighbours_table()}

    if autostart:
        if daemon:
            t = threading.Thread(target=app.run,
                                 kwargs=kwargs,
                                 daemon=True)
            t.start()
        else:
            app.run(**kwargs)
    return app


if __name__ == '__main__':
    import zigate
    zigate_instance = zigate.connect('fake')
    start_adminpanel(zigate_instance, daemon=False, quiet=False, debug=True)
