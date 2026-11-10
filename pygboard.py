#!/usr/bin/python3

import datetime as dt
import socket
import threading

import pyglet
from rich.console import Console
from rich.table import Table

from job import Job

# Job contains serial, instrument, ball_count, balls[4], attr_count, attrs[4], seconds_done, status
# '1,1,4,1,1,1,1,0,0,0,0,0,0,queued'

# Disable shadow window
pyglet.options.shadow_window = False

# Query the best config for the screen
display = pyglet.display.get_display()
screen = display.get_default_screen()
config = screen.get_best_config()

# Specify that we want to use OpenGL ES 3.1
# This is very specific to the Raspberry Pi 4 and 5. Use 3.2 if you can.
config.opengl_api = "gles"
config.major_version = 3
config.minor_version = 1

H1_LABEL_X = 100
# JOB_ICON_X = 120
JOB_COLUMN_WIDTH = 300
JOB_FONT_SIZE = 32  # 24px high
JOB_ICON_Z = 0
JOB_ICON_HEIGHT = 100
JOB_ICON_WIDTH = 100
JOB_V_SPACE = 110
H1_FONT_SIZE = 36  # 48px high
H1_LABEL_HEIGHT = 48
Q_BLOCK_TOP_Y = 1800
R_BLOCK_TOP_Y = 1000
P_BLOCK_TOP_Y = 800
D_BLOCK_TOP_Y = 400

agitator_icon = pyglet.image.load("images/agi_100.png")
formulator_icon = pyglet.image.load("images/for_100.png")
compressor_icon = pyglet.image.load("images/com_100.png")
instrument_icons = {"1": formulator_icon, "2": agitator_icon, "3": compressor_icon}

queued_job_sprites = []
delivering_job_sprite = None
processing_job_sprites = []
done_job_sprites = []
# job_icon_sprite_batch = pyglet.graphics.Batch()


def list_to_col(lst, column_length):
    # Split a list of jobs into columns for display
    return [lst[i : i + column_length] for i in range(0, len(lst), column_length)]


class StatusSectionBackground:
    def __init__(
        self, x, y, width, height, label_text, color
    ):  # color should be RGB tuple like (55, 55, 255)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.sprite_box_top = (self.y + self.height) - H1_LABEL_HEIGHT
        self.batch = pyglet.graphics.Batch()
        self.label = pyglet.text.Label(
            label_text,
            font_name="Impact",
            font_size=H1_FONT_SIZE,
            x=self.x + 20,
            y=((self.y + self.height) - H1_LABEL_HEIGHT),
            batch=self.batch,
        )
        self.color = color
        self.border = pyglet.shapes.Rectangle(
            x=self.x,
            y=self.y,
            height=self.height,
            width=self.width,
            color=self.color,
            batch=self.batch,
        )
        self.sprite_box = pyglet.shapes.Rectangle(
            x=self.x + 10,
            y=self.y + 10,
            height=(self.height - 20 - H1_LABEL_HEIGHT),
            width=self.width - 20,
            color=(255, 255, 255),
            batch=self.batch,
        )

    def draw(self):
        self.batch.draw()


class RobotStatusWindow(pyglet.window.Window):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # The height of each of these is the y of the thing above minus their y. 1920 - 1000 first, 1000-800 next.
        self.queued_section = StatusSectionBackground(
            x=0,
            y=1000,
            width=1080,
            height=920,
            label_text="Queued Jobs",
            color=(255, 80, 80),
        )
        self.delivering_section = StatusSectionBackground(
            x=0,
            y=800,
            width=1080,
            height=200,
            label_text="Delivering Job",
            color=(0, 255, 0),
        )
        self.processing_section = StatusSectionBackground(
            x=0,
            y=400,
            width=1080,
            height=400,
            label_text="Processing Jobs",
            color=(0, 0, 255),
        )
        self.done_section = StatusSectionBackground(
            x=0,
            y=0,
            width=1080,
            height=400,
            label_text="Recently Completed Jobs",
            color=(128, 128, 128),
        )
        self.sections = [
            self.queued_section,
            self.delivering_section,
            self.processing_section,
            self.done_section,
        ]

        self.queued_job_sprites = []
        self.delivering_job_sprite = None
        self.processing_job_sprites = []
        self.done_job_sprites = []
        self.job_text_labels = []
        self.job_icon_sprite_batch = pyglet.graphics.Batch()
        self.job_text_labels_batch = pyglet.graphics.Batch()

    def update_lists(self):
        print("Updating lists")

        # Empty the existing data
        self.queued_job_sprites = []
        self.delivering_job_sprite = None
        self.processing_job_sprites = []
        self.done_job_sprites = []
        self.job_text_labels = []
        self.job_icon_sprite_batch = pyglet.graphics.Batch()
        self.job_text_labels_batch = pyglet.graphics.Batch()

        with queued_jobs_lock:
            queued_columns = list_to_col(list(queued_jobs.values()), 3)
            for c, col in enumerate(queued_columns, start=0):
                for i, job in enumerate(col, start=1):
                    self.queued_job_sprites.append(
                        pyglet.sprite.Sprite(
                            img=instrument_icons[job.instrument],
                            x=20 + (c * JOB_COLUMN_WIDTH),
                            y=(
                                self.queued_section.sprite_box_top - (i * (JOB_V_SPACE))
                            ),
                            batch=self.job_icon_sprite_batch,
                        )
                    )
                    self.job_text_labels.append(
                        pyglet.text.Label(
                            job.serial,
                            font_name="Impact",
                            font_size=JOB_FONT_SIZE,
                            x=100 + 40 + 20 + (c * JOB_COLUMN_WIDTH),
                            y=(
                                self.queued_section.sprite_box_top - (i * (JOB_V_SPACE))
                            ),
                            color=(0, 0, 0),
                            batch=self.job_text_labels_batch,
                        )
                    )
        with delivering_job_lock:
            if delivering_job:
                self.delivering_job_sprite = pyglet.sprite.Sprite(
                    img=instrument_icons[delivering_job.instrument],
                    x=20,
                    y=(self.delivering_section.sprite_box_top - (JOB_V_SPACE)),
                    batch=self.job_icon_sprite_batch,
                )
                self.job_text_labels.append(
                    pyglet.text.Label(
                        delivering_job.serial,
                        font_name="Impact",
                        font_size=JOB_FONT_SIZE,
                        x=100 + 40 + 20,
                        y=(self.delivering_section.sprite_box_top - JOB_V_SPACE),
                        color=(0, 0, 0),
                        batch=self.job_text_labels_batch,
                    )
                )
        with processing_jobs_lock:
            processing_columns = list_to_col(list(processing_jobs.values()), 3)
            for (
                c,
                col,
            ) in enumerate(processing_columns, start=0):
                for i, job in enumerate(col, start=1):
                    self.processing_job_sprites.append(
                        pyglet.sprite.Sprite(
                            img=instrument_icons[job.instrument],
                            x=20 + (c * JOB_COLUMN_WIDTH),
                            y=(
                                self.processing_section.sprite_box_top
                                - (i * (JOB_V_SPACE))
                            ),
                            batch=self.job_icon_sprite_batch,
                        )
                    )
                    self.job_text_labels.append(
                        pyglet.text.Label(
                            job.serial,
                            font_name="Impact",
                            font_size=JOB_FONT_SIZE,
                            x=100 + 40 + 20 + (c * JOB_COLUMN_WIDTH),
                            y=(
                                self.processing_section.sprite_box_top
                                - (i * (JOB_V_SPACE))
                            ),
                            color=(0, 0, 0),
                            batch=self.job_text_labels_batch,
                        )
                    )
        with done_jobs_lock:
            done_columns = list_to_col(list(done_jobs.values()), 3)
            for c, col in enumerate(done_columns, start=0):
                for i, job in enumerate(col, start=1):
                    self.done_job_sprites.append(
                        pyglet.sprite.Sprite(
                            img=instrument_icons[job.instrument],
                            x=20 + (c * JOB_COLUMN_WIDTH),
                            y=(self.done_section.sprite_box_top - (i * (JOB_V_SPACE))),
                            batch=self.job_icon_sprite_batch,
                        )
                    )

                    self.job_text_labels.append(
                        pyglet.text.Label(
                            job.serial,
                            font_name="Impact",
                            font_size=JOB_FONT_SIZE,
                            x=100 + 40 + 20 + (c * JOB_COLUMN_WIDTH),
                            y=(self.done_section.sprite_box_top - (i * (JOB_V_SPACE))),
                            color=(0, 0, 0),
                            batch=self.job_text_labels_batch,
                        )
                    )

    def on_draw(self):
        # global new_job_received
        if new_job_received.is_set():
            self.update_lists()
            new_job_received.clear()
        self.clear()
        for section in self.sections:
            section.draw()
        self.job_icon_sprite_batch.draw()
        self.job_text_labels_batch.draw()


main_window = RobotStatusWindow(
    config=config, caption="Robot Status", width=1080, height=1920
)
main_window.set_fullscreen(True)

console = Console()

client_list = []
socket_lock = threading.Lock()
message_log = []

queued_jobs = {}
delivering_job = None
processing_jobs = {}
done_jobs = {}
queued_jobs_lock = threading.Lock()
delivering_job_lock = threading.Lock()
processing_jobs_lock = threading.Lock()
done_jobs_lock = threading.Lock()
new_job_received = threading.Event()


def print_table():
    # global queued_jobs
    # global delivering_job
    # global processing_jobs
    # global done_jobs
    # global queued_jobs_lock
    # global delivering_job_lock
    # global processing_jobs_lock
    # global done_jobs_lock

    # Build table for terminal display
    table = Table(f"Robot Job Status at {dt.datetime.now().strftime('%H:%M:%S %f')}")
    queued_table = Table("Queued", show_header=True, style="magenta")  # , box=None)
    delivering_table = Table(
        "Delivering", show_header=True, style="cyan"
    )  # , box=None)
    processing_table = Table(
        "Processing", show_header=True, style="yellow"
    )  # , box=None)
    done_table = Table("Done", show_header=True, style="green")  # , box=None)
    table.add_row(queued_table)
    table.add_row(delivering_table)
    table.add_row(processing_table)
    table.add_row(done_table)

    # Fill table with items from job variables
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
    #    console.clear() # Wipe the console of the last-drawn table
    print("\n\n")
    console.print(table)
    console.bell()


def handle_client(conn, addr):
    # global queued_jobs
    global delivering_job
    # global processing_jobs
    # global done_jobs
    # global queued_jobs_lock
    # global delivering_job_lock
    # global processing_jobs_lock
    # global done_jobs_lock
    # global new_job_received

    with socket_lock:
        client_list.append(addr)
    print("=" * 80)
    print(f"Connection from: {addr} at {dt.datetime.now().strftime('%H:%M:%S %f')}")
    try:
        while True:
            data = conn.recv(1024)
            if not data:  # empty bytes mean the client closed the connection
                break
            conn.sendall(data)  # echo the received data back to the clent
            with socket_lock:
                rx_job = Job(data.decode("utf-8"))
                print(f"Job status change received for {rx_job}")
                if rx_job.status == "queued":
                    with queued_jobs_lock:
                        queued_jobs[rx_job.serial] = rx_job
                    print(f"Added to queued: {rx_job}")
                if rx_job.status == "delivering":
                    # print(f"Current queued keys: {queued_jobs.keys()}")
                    # print(f"Removing from queued to add to delivering: {queued_jobs.pop(rx_job.serial)}")
                    with queued_jobs_lock:
                        queued_jobs.pop(rx_job.serial)
                    with delivering_job_lock:
                        delivering_job = rx_job
                        print(f"Delivering job rx'd: {delivering_job}")
                if rx_job.status == "processing":
                    with delivering_job_lock:
                        if rx_job.serial == delivering_job.serial:
                            # print(f"Removed from delivering to add to processing: {delivering_job}")
                            delivering_job = None
                    with processing_jobs_lock:
                        processing_jobs[rx_job.serial] = rx_job
                if rx_job.status == "done":
                    # print(f"Removed from processing to add to done: {processing_jobs.pop(rx_job.serial)}")
                    with processing_jobs_lock:
                        processing_jobs.pop(rx_job.serial)
                    with done_jobs_lock:
                        done_jobs[rx_job.serial] = rx_job
                print_table()
                new_job_received.set()
    except (ConnectionResetError, BrokenPipeError) as e:
        print(f"Connection error with {addr}: {e}")
    finally:
        conn.close()


def server_program():
    host = "192.168.125.202"  # address on robot network
    # host = '' # host on all IP addresses available
    # host = '127.0.0.1' # Loopback address for local testing
    port = 65432

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # IPV4 TCP Socket
    server_socket.setsockopt(
        socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
    )  # allow port reuse
    server_socket.bind((host, port))
    server_socket.listen(5)  # Queue up to 5 connection requests
    print(f"Server listening on {host}:{port}")

    try:
        while True:
            conn, addr = server_socket.accept()
            socket_connection_thread = threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            )
            socket_connection_thread.start()
            print(f"Active connections: {threading.active_count() - 1}")
    except KeyboardInterrupt:
        print("Server shutting down")
    finally:
        server_socket.close()


# if __name__ == '__main__':
socket_server_thread = threading.Thread(target=server_program, daemon=False)
socket_server_thread.start()
pyglet.app.run()
