import socket
import threading
import pprint
from rich.console import Console
from rich.table import Table

# Job contains serial, instrument, ball_count, balls[4], attr_count, attrs[4], seconds_done, status
# TODO: Have robot send full job as text, parse in python and print.

table = Table(title="Robot Job Status")
table.add_column("Queued", justify="left", style="cyan", no_wrap=False)
table.add_column("Delivering", justify="left", style="magenta", no_wrap=False)
table.add_column("Processing", justify="left", style="blue", no_wrap=False)
table.add_column("Done", justify="left", style="green", no_wrap=False)
queued_table = Table()
delivering_table = Table()
processing_table = Table()
done_table = Table()
table.add_row(queued_table, delivering_table, processing_table, done_table)

console = Console()

client_list = []
lock = threading.Lock()
message_log = []

queued_jobs = {}
delivering_job = ""
processing_jobs = {}
done_jobs = {}


def print_table():
    for job in queued_jobs:
        queued_table.add_row(job)
    delivering_table.add_row(delivering_job)
    for job in processing_jobs:
        processing_table.add_row(job)
    for job in done_jobs:
        done_table.add_row(job)
    console.print(table)
    

def handle_client(conn, addr):
    with lock:
        client_list.append(addr)
    print(f"Connection from: {addr}")
    try:
        while True:
            data = conn.recv(1024)
            if not data: #empty bytes mean the client closed the connection
                break
            conn.sendall(data) #echo the received data back to the clent
            with lock:
                message_log.append(data)
                pprint.pp(message_log)
                print_table()
    except (ConnectionResetError, BrokenPipeError) as e:
        print (f"Connection error with {addr}: {e}")
    finally:
        conn.close()


def server_program():
    host = '192.168.125.203' # Loopback address for local testing
    port = 65432

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # IPV4 TCP Socket
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # allow port reuse
    server_socket.bind((host, port))
    server_socket.listen(5) # Queue up to 5 connection requests
    print(f"Server listening on {host}:{port}")

    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn,addr), daemon=True)
            thread.start()
            print(f"Active connections: {threading.active_count() -1}")
    except KeyboardInterrupt:
        print("Server shutting down")
    finally:
        server_socket.close()

if __name__ == '__main__':
    server_program()
