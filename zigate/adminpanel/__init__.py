#
# Copyright (c) 2018 Sébastien RAMAGE
#
# For the full copyright and license information, please view the LICENSE
# file that was distributed with this source code.
#

import threading
from bottle import Bottle, route, run, view, template  # noqa

ADMINPANEL_PORT = 9998


def start_adminpanel(zigate_instance, port=ADMINPANEL_PORT, daemon=True, quiet=True):
    app = Bottle()
    app.zigate = zigate_instance

    @app.route('/')
    @view('index')
    def index():
        from zigate import version
        return {'port': zigate_instance._port,
                'libversion': version.__version__,
                'version': zigate_instance.get_version_text(),
                'connected': zigate_instance.connection.is_connected(),
                'devices': zigate_instance.devices
                }

    @app.route('/networkmap')
    @view('networkmap')
    def networkmap():
        return

    kwargs = {'host': '0.0.0.0', 'port': port,
              'quiet': quiet}
    if daemon:
        t = threading.Thread(target=app.run,
                             kwargs=kwargs,
                             daemon=True)
        t.start()
    else:
        app.run(**kwargs)


if __name__ == '__main__':
    from unittest import mock
    zigate_instance = mock.MagicMock()
    start_adminpanel(zigate_instance, daemon=False, quiet=False)
