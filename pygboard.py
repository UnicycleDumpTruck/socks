#!/usr/bin/python3

import pyglet
import random
import datetime as dt
import socket
import threading
import pprint
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
config.fullscreen = True

H1_LABEL_X = 100
JOB_ICON_X = 120
JOB_ICON_Z = 0
JOB_ICON_HEIGHT = 100
JOB_ICON_WIDTH = 100
JOB_V_SPACE = 20
H1_FONT_SIZE = 36
H1_LABEL_HEIGHT = 48
Q_BLOCK_TOP_Y = 1800
R_BLOCK_TOP_Y = 1000
P_BLOCK_TOP_Y = 800
D_BLOCK_TOP_Y = 400

agitator_icon = pyglet.image.load('agi_100.png')
formulator_icon = pyglet.image.load('for_100.png')
compressor_icon = pyglet.image.load('com_100.png')
instrument_icons = {'1':formulator_icon, '2':agitator_icon, '3':compressor_icon}

queued_job_sprites = []
delivering_job_sprite = None
processing_job_sprites = []
done_job_sprites = []
job_icon_sprite_batch = pyglet.graphics.Batch()

class StatusSectionBackground():
  def __init__(self, x, y, width, height, label_text, color): # color should be RGB tuple like (55, 55, 255)
    self.x = x
    self.y = y
    self.width = width
    self.height = height
    self.batch = pyglet.graphics.Batch()
    self.label = pyglet.text.Label(label_text, font_name='Impact',
                                   font_size=H1_FONT_SIZE, 
                                   x=self.x + 20, 
                                   y=((self.y + self.height) - H1_LABEL_HEIGHT), 
                                   batch=self.batch)
    self.color = color
    self.border = pyglet.shapes.Rectangle(x=self.x, y=self.y, height=self.height, width=self.width, color=self.color, batch=self.batch)
  def draw(self):
    self.batch.draw()

class RobotStatusWindow(pyglet.window.Window):
  def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.sections = [StatusSectionBackground(x=0,y=1000,width=1080,height=920,label_text='Queued Jobs Section',color=(255,55,55)),]
    # self.queued_label = pyglet.text.Label('Queued Jobs', font_name='Impact',
    #                       font_size=36, x=H1_LABEL_X, y=Q_BLOCK_TOP_Y)
    self.delivering_label = pyglet.text.Label('Delivering Job', font_name='Impact',
                          font_size=36, x=H1_LABEL_X, y=R_BLOCK_TOP_Y)
    self.processing_label = pyglet.text.Label('Processing Jobs', font_name='Impact',
                          font_size=36, x=H1_LABEL_X, y=P_BLOCK_TOP_Y)
    self.done_label = pyglet.text.Label('Done Jobs', font_name='Impact',
                          font_size=36, x=H1_LABEL_X, y=D_BLOCK_TOP_Y)
    self.labels = [self.delivering_label, self.processing_label, self.done_label, self.done_label]
       
    self.queued_job_sprites = []
    self.delivering_job_sprite = None
    self.processing_job_sprites = []
    self.done_job_sprites = []
    self.job_icon_sprite_batch = pyglet.graphics.Batch()

    print('Main status window init complete')
  def update_lists(self):
    print("Updating lists")

    # Empty the existing data
    self.queued_job_sprites = []
    self.delivering_job_sprite = None
    self.processing_job_sprites = []
    self.done_job_sprites = []
    self.job_icon_sprite_batch = pyglet.graphics.Batch()
    
    with queued_jobs_lock:
      for i, job in enumerate(queued_jobs.items()):
        self.queued_job_sprites.append(
          pyglet.sprite.Sprite(img=instrument_icons[job[1].instrument], 
                              x=JOB_ICON_X, 
                              y=(Q_BLOCK_TOP_Y - H1_LABEL_HEIGHT - (i * (JOB_ICON_HEIGHT + JOB_V_SPACE))),
                              batch=self.job_icon_sprite_batch))
    with delivering_job_lock:
      if delivering_job:
        self.delivering_job_sprite = pyglet.sprite.Sprite(img=instrument_icons[delivering_job.instrument], 
                              x=JOB_ICON_X, 
                              y=(R_BLOCK_TOP_Y - H1_LABEL_HEIGHT - (JOB_ICON_HEIGHT + JOB_V_SPACE)),
                              batch=self.job_icon_sprite_batch)
    with processing_jobs_lock:
      for i, job in enumerate(processing_jobs.items()):
          self.processing_job_sprites.append(
            pyglet.sprite.Sprite(img=instrument_icons[job[1].instrument], 
                              x=JOB_ICON_X, 
                              y=(P_BLOCK_TOP_Y - H1_LABEL_HEIGHT - (i * (JOB_ICON_HEIGHT + JOB_V_SPACE))),
                              batch=self.job_icon_sprite_batch))
    with done_jobs_lock:
      for i, job in enumerate(done_jobs.items()):
          self.done_job_sprites.append(
            pyglet.sprite.Sprite(img=instrument_icons[job[1].instrument], 
                              x=JOB_ICON_X, 
                              y=(D_BLOCK_TOP_Y - H1_LABEL_HEIGHT - (i * (JOB_ICON_HEIGHT + JOB_V_SPACE))),
                              batch=self.job_icon_sprite_batch))

  def on_draw(self):
    global new_job_received
    if new_job_received.is_set():
      self.update_lists()
      new_job_received.clear()
    self.clear()
    for section in self.sections:
      section.draw()
    for lbl in self.labels:
      lbl.draw()
    self.job_icon_sprite_batch.draw()


main_window = RobotStatusWindow(config=config, caption="Robot Status", width=1080, height=1920)
main_window.set_fullscreen(True)

console = Console()

client_list = []
lock = threading.Lock()
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
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs
    global queued_jobs_lock
    global delivering_job_lock
    global processing_jobs_lock
    global done_jobs_lock

    # Build table for terminal display
    table = Table(f"Robot Job Status at {dt.datetime.now().strftime("%H:%M:%S %f")}")
    queued_table = Table("Queued", show_header=True, style="magenta")#, box=None)
    delivering_table = Table("Delivering", show_header=True, style="cyan")#, box=None)
    processing_table = Table("Processing", show_header=True, style="yellow")#, box=None)
    done_table = Table("Done", show_header=True, style="green")#, box=None)
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
    console.clear() # Wipe the console of the last-drawn table
    print("\n\n")
    console.print(table)
    console.bell()

def print_job_summary():
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs
    global queued_jobs_lock
    global delivering_job_lock
    global processing_jobs_lock
    global done_jobs_lock
    print(f"Job summary at {dt.datetime.now().strftime("%H:%M:%S %f")}")
    print("queued_jobs:")
    with queued_jobs_lock:
      print(queued_jobs)
    with delivering_job_lock:
      print(f"delivering_job {delivering_job}")
    print("processing_jobs")  
    with processing_jobs_lock:  
      print(processing_jobs)
    print("done_jobs")
    with done_jobs_lock:
      print(done_jobs)

def handle_client(conn, addr):
    global queued_jobs
    global delivering_job
    global processing_jobs
    global done_jobs
    global queued_jobs_lock
    global delivering_job_lock
    global processing_jobs_lock
    global done_jobs_lock
    global new_job_received

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
        print (f"Connection error with {addr}: {e}")
    finally:
        conn.close()


def server_program():
    host = '192.168.125.202' # Loopback address for local testing
    #host = '' # Loopback address for local testing
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
            socket_connection_thread = threading.Thread(target=handle_client, args=(conn,addr), daemon=True)
            socket_connection_thread.start()
            print(f"Active connections: {threading.active_count() -1}")
    except KeyboardInterrupt:
        print("Server shutting down")
    finally:
        server_socket.close()

#if __name__ == '__main__':
socket_server_thread = threading.Thread(target=server_program, daemon=False)
socket_server_thread.start()
pyglet.app.run()
