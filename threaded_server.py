import socket
import threading
import pprint
from rich.console import Console
from rich.table import Table
from job import Job

# Job contains serial, instrument, ball_count, balls[4], attr_count, attrs[4], seconds_done, status
# TODO: Have robot send full job as text, parse in python and print.
# '1,1,4,1,1,1,1,0,0,0,0,0,0,queued'


console = Console()

client_list = []
lock = threading.Lock()
message_log = []

queued_jobs = {}
delivering_job = None
processing_jobs = {}
done_jobs = {}


def print_table():
    table = Table(title="Robot Job Status")
    table.add_column("Queued", justify="left", style="cyan", no_wrap=False)
    table.add_column("Delivering", justify="left", style="magenta", no_wrap=False)
    table.add_column("Processing", justify="left", style="blue", no_wrap=False)
    table.add_column("Done", justify="left", style="green", no_wrap=False)
    queued_table = Table(show_header=False, box=None)
    delivering_table = Table(show_header=False, box=None)
    processing_table = Table(show_header=False, box=None)
    done_table = Table(show_header=False, box=None)
    table.add_row(queued_table, delivering_table, processing_table, done_table)

    for job in queued_jobs.items():
        print(f"adding to queued: {job[1].str()}")
        queued_table.add_row(job[1].str())
    if delivering_job:
        print(f"adding to delivering: {delivering_job.str()}")
        delivering_table.add_row(delivering_job.str())
    for job in processing_jobs.items():
        print(f"adding to proc: {job[1].str()}")
        processing_table.add_row(job[1].str())
    for job in done_jobs.items():
        print(f"adding to done: {job[1].str()}")
        done_table.add_row(job[1].str())
    delivering_table.add_row("test")
    console.print(table)
    print(delivering_job)
    

def handle_client(conn, addr):
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs

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
                rx_job = Job(data.decode("utf-8"))
                print(f"new job: {rx_job}")
                if rx_job.status == "queued":
                    queued_jobs[rx_job.serial] = rx_job
                if rx_job.status == "delivering":
                    delivering_job = rx_job
                    print(f"Delivering job rx'd: {delivering_job}")

                if rx_job.status == "processing":
                    processing_jobs[rx_job.serial] = rx_job
                    print(processing_jobs)
                if rx_job.status == "done":
                    done_jobs[rx_job.serial] = rx_job
                    print(done_jobs)
                print_table()
    except (ConnectionResetError, BrokenPipeError) as e:
        print (f"Connection error with {addr}: {e}")
    finally:
        conn.close()


def server_program():
    # host = '192.168.125.203' # Loopback address for local testing
    host = '127.0.0.1' # Loopback address for local testing
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
