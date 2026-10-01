import socket

def client_program():
    host = '192.168.125.203' # loopback address for testing
    port = 65432

    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # IPv4 TCP socket
    client_socket.connect((host, port)) #connect to the server

    message = input("'quit' or text to send -> ") # take input

    while message.lower().strip() != 'quit':
        client_socket.sendall(message.encode()) # send message
        raw = client_socket.recv(1024) # read up to 1024 bytes
        if not raw:
            break
        try:
            data = raw.decode('utf-8')
        except UnicodeDecodeError:
            print("Received non-UTF-8 data from server, skipping.")
            continue

        print('Received from server: ' + data) # show in terminal

        message = input(" -> ") # again take input

    client_socket.close() # close the connection

if __name__ == '__main__':
    client_program()
