'''
Created on 31 janv. 2018

@author: sramage
'''
import threading
import socket
import sys


class Broker(threading.Thread):
    def __init__(self, zigate, port=9999, host='0.0.0.0'):
        threading.Thread.__init__(self)
        self.zigate = zigate
        self.zigate.decode_data = self.forward_msg
        self.port = port
        self.host = host
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.users = []

        try:
            self.server.bind((self.host, self.port))
        except socket.error:
            print('Bind failed %s' % (socket.error))
            sys.exit()

        self.server.listen()

    def exit(self):
        self.zigate.close()
        self.server.close()

    def forward_msg(self, raw_message):
        raw_message = raw_message
        to_remove = []
        for conn, addr in self.users:
            try:
                conn.sendall(raw_message)
            except:
                to_remove.append((conn, addr))
        for d in to_remove:
            self.users.remove(d)

    def run_thread(self, conn, addr):
        print('Client connected with ' + addr[0] + ':' + str(addr[1]))
        while True:
            data = conn.recv(1024)
            self.zigate.send_to_transport(data)
        conn.close()

    def run(self):
        print('Waiting for connections on port %s' % (self.port))
        # We need to run a loop and create a new thread for each connection
        while True:
            conn, addr = self.server.accept()
            self.users.append((conn, addr))
            threading.Thread(target=self.run_thread, args=(conn, addr)).start()


if __name__ == '__main__':
    from zigate.core import ZiGate
    import logging
    logging.basicConfig()
    logging.root.setLevel(logging.DEBUG)
    z = ZiGate(auto_start=False)
    server = Broker(z)
    server.run()
