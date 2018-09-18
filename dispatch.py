from threading import Thread
from struct import pack, unpack
from select import select, error
from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR

class Dispatch(Thread):
    def __init__(self, host, port, parser):
        Thread.__init__(self)

        self.host = host
        self.port = port
        self.running = True
        self.parser = parser
        self.clients = list()
        self.connections = 5
        self.end_of_line = "\r\n"
        self.buffer_size = 4096

    def bind(self):
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(self.connections)
        self.clients.append(self.sock)

    def send(self, sock, message, *args):
        response = message.format(*args) + self.end_of_line
        sock.send(response.encode())

    def receive(self, sock):
        data = ""
        while self.end_of_line not in data:
            chunk = sock.recv(self.buffer_size)

            if not chunk:
                data = None
                break
            else:
                data = data + chunk.decode()

        return data.strip(self.end_of_line)

    def broadcast(self, client_sock, client_message):
        for sock in self.clients:
            not_server = (sock != self.sock)
            not_sending_client = (sock != client_sock)
            if not_server and not_sending_client:
                try:
                    self.send(sock, client_message)
                except error:
                    sock.close()
                    self.clients.remove(sock)

    def run(self):
        self.bind()
        while self.running:
            try:
                selection = select(self.clients, list(), list(), 5)
                read_sock, write_sock, error_sock = selection
            except error:
                pass
            
            for sock in read_sock:
                if sock == self.sock:
                    try:
                        accept_sock = self.sock.accept()
                        client_sock, client_address = accept_sock
                        client_sock.settimeout(60)
                    except error:
                        break
                    
                    print("[%s:%s] '%s:%s' now online" % 
                        (self.host, self.port, *client_address))
                    self.clients.append(client_sock)
                    self.broadcast(client_sock, encode({
                        "name": "connected",
                        "data": client_address
                    }))
                else:
                    address = sock.getpeername()
                    try:
                        message = self.receive(sock)
                        if message:
                            print("[%s:%s] %s" % (*address, message))
                            self.parser(self, sock, message)
                    except error:
                        sock.close()
                        self.clients.remove(sock)
                        continue

    def quit(self):
        self.running = False
        self.sock.close()

# USAGE:
#
# def parser(server, sock, message):
#     server.send(sock, message[::-1])
#
# server = Dispatch("127.0.0.1", 10301, parser)
# server.start()