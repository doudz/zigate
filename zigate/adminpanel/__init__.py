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
        return

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
    start_adminpanel(None, daemon=False, quiet=False)
