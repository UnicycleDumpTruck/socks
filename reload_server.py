#!/usr/bin/env python3
import socket
import threading
import os
import hashlib
import base64
import time

import ctypes
import select
import fcntl
import termios
import signal


WEBSOCKET_PATH = "/websocket"
MAX_REQUEST_LENGTH = 8*1024
WEBSOCKET_MAGIC_KEY = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'

EXTRA_INDEX_DATA = '''
<script>
addEventListener('DOMContentLoaded', function() {
    const socket = new WebSocket('ws://LISTENING_HOST_REPLACE:LISTENING_PORT_REPLACE/websocket');
    socket.addEventListener('message', function (event) {
        socket.close();
        window.location.reload();
    });
});
</script>
'''

class SmallINotify():
    class Flags():
        # NOTE: Values from inotify.h. There are more values but these are the ones we can wait on
        ACCESS        = 0x00000001    # File was accessed.
        MODIFY        = 0x00000002    # File was modified.
        ATTRIB        = 0x00000004    # Metadata changed.
        CLOSE_WRITE   = 0x00000008    # Writtable file was closed.
        CLOSE_NOWRITE = 0x00000010    # Unwrittable file closed.
        OPEN          = 0x00000020    # File was opened.
        MOVED_FROM    = 0x00000040    # File was moved from X.
        MOVED_TO      = 0x00000080    # File was moved to Y.
        CREATE        = 0x00000100    # Subfile was created.
        DELETE        = 0x00000200    # Subfile was deleted.
        DELETE_SELF   = 0x00000400    # Self was deleted.
        MOVE_SELF     = 0x00000800    # Self was moved.

    def __init__(self):
        try: libc_so = ctypes.util.find_library('c')
        except: libc_so = None
        self._libc = ctypes.CDLL(libc_so or 'libc.so.6', use_errno=True)
        self._inotify_event_queue_fd = self._libc_call(self._libc.inotify_init)
        self._poller = select.poll()
        self._poller.register(self._inotify_event_queue_fd)

    def _libc_call(self, function, *args):
        # TODO: error check for intterupts?. EINTR
        return_code = function(*args)
        return return_code

    def read(self):
        data = self._readall()
        timeout = -1
        if not data  and self._poller.poll(timeout):
            data = self._readall()
        return len(data) # TODO: Actually parse data and return list of events?

    def _readall(self):
        bytes_avail = ctypes.c_int()
        fcntl.ioctl(self._inotify_event_queue_fd, termios.FIONREAD, bytes_avail)
        if not bytes_avail.value:
            return b''
        return os.read(self._inotify_event_queue_fd, bytes_avail.value)

    def add_watch(self, path, mask):
        return self._libc_call(self._libc.inotify_add_watch, self._inotify_event_queue_fd, os.fsencode(path), mask)

    def add_watch_recursive(self, root, mask):
        # TODO: Add exclude dirs. Remove '.git', maybe all hidden files and just add a param to filter
        self.add_watch(root, mask)
        for current_root, dirs, files in os.walk(root):
            for _dir in dirs:
                dir_path = os.path.join(current_root, _dir)
                self.add_watch(dir_path, mask)



class Server:
    def __init__(self, host = "localhost", listen_port = 5000):
        self.host = host
        self.listen_port = listen_port
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind((host, self.listen_port)) 
        self.listen_socket.listen(10)
        self.event_obj = threading.Event()


        print("serving content on {}:{}".format(host, listen_port));

        inotify = SmallINotify()
        watch_flags = inotify.Flags.CREATE | inotify.Flags.MODIFY  | inotify.Flags.DELETE
        wd = inotify.add_watch('.', watch_flags)

        thread = threading.Thread(target = self.check_filechanges_loop, args=(inotify,))
        thread.start()

        while True:
            client_socket, client_address = self.listen_socket.accept()
            thread = threading.Thread(
                target = self.process_request,
                args = (client_socket, client_address, self.event_obj),
            )
            thread.start()


    def check_filechanges_loop(self, inotify):
        while True:
            inotify.read() # NOTE: Read all events
            print('--------: Event');
            self.event_obj.set()

        # while True:
        #     time.sleep(2)
        #     self.event_obj.set()

    def process_file_request(self, client_socket, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'rb') as f:
                data = f.read()
            if file_path == 'index.html':
                new_data = EXTRA_INDEX_DATA
                new_data = new_data.replace('LISTENING_HOST_REPLACE', str(self.host))
                new_data = new_data.replace('LISTENING_PORT_REPLACE', str(self.listen_port))
                data += new_data.encode()
            self.send_response(client_socket, 200, 'OK', "text/html", data)
            print('served: {}'.format(file_path))
        else:
            output_data = "File {} not found".format(file_path)
            message = "File not found"
            self.send_response(client_socket, 404, message, "text/html", output_data.encode())
            print('Not found: {}'.format(file_path))

    def websocket_init_and_process(self, client_socket, headers):
        # TODO: Verify that request is correct websocket initialization request

        client_key = headers.get('sec-websocket-key', '')
        combined_key = client_key + WEBSOCKET_MAGIC_KEY
        hashed_combined_key = hashlib.sha1(combined_key.encode())
        encoded_key = base64.b64encode(hashed_combined_key.digest())

        output = "HTTP/1.1 {} {}\r\n".format(101, "Switching protocols")
        output += "Upgrade: Websocket\r\n"
        output += "Connection: Upgrade\r\n"
        output += "Sec-WebSocket-Accept: {}\r\n".format(encoded_key.decode())
        output += "\r\n"

        client_socket.send(output.encode())

        message = 'reload'
        message_data = bytes([
            0b10000001,  # Type TEXT
            len(message),
        ])
        message_data += message.encode()

        try:
            while self.event_obj.wait():
                client_socket.send(message_data)
                self.event_obj.clear() # TODO: This synchronization method is stupid. But good enough for now. Move everything to select(...)
        except:
            pass # NOTE: Client probably refreshed and closed the socket.

    def headers_str_to_map(self, headers_str):
        lines = headers_str.split('\r\n')
        result = {}
        for line in lines[1:]:
            key, value = line.split(':', 1)
            result[key.lower()] = value.strip()
        return result


    def process_request(self, client_socket, client_address, event_obj):
        # TODO: Do it in a loop
        request_str = client_socket.recv(MAX_REQUEST_LENGTH)
        request_str = request_str.decode('utf-8')

        #TODO: break if no parts available
        parts = request_str.split('\r\n\r\n')

        raw_headers = parts[0]
        raw_body = parts[1]

        header_parts =  raw_headers.split('\r\n')
        request_line = header_parts[0]

        method, path, http_version = request_line.split(' ')

        if path == WEBSOCKET_PATH:
            headers = self.headers_str_to_map(raw_headers)
            self.websocket_init_and_process(client_socket, headers)
        else:
            file_path = self.get_file_path(path)
            self.process_file_request(client_socket, file_path)

        client_socket.close()

    def send_response(self, client_socket, code, message, content_type, data):
        output = "HTTP/1.1 {} {}\r\n".format(code, message)
        # output += b"Content-Type: {}\r\n".format(content_type,)
        output += "\r\n"
        output = output.encode()
        output += data

        client_socket.send(output)

    def get_file_path(self, path):
        file_path = path[1:]
        if path == '/':
            file_path = 'index.html'
        return file_path

def signal_handler(sig, frame):
    os._exit(1)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal_handler)
    Server()
