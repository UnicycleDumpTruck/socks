import datetime as dt
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
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs
    table = Table(f"Robot Job Status at {dt.datetime.now().strftime("%H:%M:%S %f")}")

    queued_table = Table("Queued", show_header=True, style="magenta")#, box=None)
    delivering_table = Table("Delivering", show_header=True, style="cyan")#, box=None)
    processing_table = Table("Processing", show_header=True, style="yellow")#, box=None)
    done_table = Table("Done", show_header=True, style="green")#, box=None)
    #table.add_row(queued_table, delivering_table, processing_table, done_table)
    #table.add_row("Queued", justify="left", style="magenta", no_wrap=False)
    table.add_row(queued_table)
    #table.add_row("Delivering", justify="left", style="cyan", no_wrap=False)
    table.add_row(delivering_table)
    #table.add_row("Processing", justify="left", style="yellow", no_wrap=False)
    table.add_row(processing_table)
    #table.add_row("Done", justify="left", style="green", no_wrap=False)
    table.add_row(done_table)

    for job in queued_jobs.items():
        print(f"adding to queued: {job[1].str()}")
        queued_table.add_row(job[1].str())
    queued_table.add_row("")
    if delivering_job:
        print(f"adding to delivering: {delivering_job.str()}")
        delivering_table.add_row(delivering_job.str())
    delivering_table.add_row("")
    for job in processing_jobs.items():
        print(f"adding to proc: {job[1].str()}")
        processing_table.add_row(job[1].str())
    processing_table.add_row("")
    for job in done_jobs.items():
        print(f"adding to done: {job[1].str()}")
        done_table.add_row(job[1].str())
    done_table.add_row("")
    console.clear()
    print("\n\n")
    console.print(table)
    console.bell()

def print_job_summary():
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs
    print(f"Job summary at {dt.datetime.now().strftime("%H:%M:%S %f")}")
    print("queued_jobs:")
    print(queued_jobs)
    print(f"delivering_job {delivering_job}")
    print("processing_jobs")
    print(processing_jobs)
    print("done_jobs")
    print(done_jobs)
    

def handle_client(conn, addr):
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs

    with lock:
        client_list.append(addr)
    print("="*80)
    print(f"Connection from: {addr} at {dt.datetime.now().strftime("%H:%M:%S %f")}")
    try:
        while True:
            data = conn.recv(1024)
            if not data: #empty bytes mean the client closed the connection
                break
            conn.sendall(data) #echo the received data back to the clent
            with lock:
                rx_job = Job(data.decode("utf-8"))
                print(f"Job status change received for {rx_job}")
                if rx_job.status == "queued":
                    queued_jobs[rx_job.serial] = rx_job
                    print(f"Added to queued: {rx_job}")
                if rx_job.status == "delivering":
                    print(f"Current queued keys: {queued_jobs.keys()}")
                    print(f"Removing from queued to add to delivering: {queued_jobs.pop(rx_job.serial)}")
                    delivering_job = rx_job
                    print(f"Delivering job rx'd: {delivering_job}")
                if rx_job.status == "processing":
                    if rx_job.serial == delivering_job.serial:
                        print(f"Removed from delivering to add to processing: {delivering_job}")
                        delivering_job = None
                    processing_jobs[rx_job.serial] = rx_job
                if rx_job.status == "done":
                    print(f"Removed from processing to add to done: {processing_jobs.pop(rx_job.serial)}")
                    done_jobs[rx_job.serial] = rx_job
                print_table()
    except (ConnectionResetError, BrokenPipeError) as e:
        print (f"Connection error with {addr}: {e}")
    finally:
        conn.close()


def server_program():
    host = '192.168.125.203' # Loopback address for local testing
    #host = '127.0.0.1' # Loopback address for local testing
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
