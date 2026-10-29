from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys
import webbrowser
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import asyncio
import websockets
import threading

port = 8000
clients = set()


async def webocket_handler(websocket):
    print("client connected")
    clients.add(websocket)
    print(clients)
    try:
        await websocket.wait_closed()
    finally:
        clients.remove(websocket)
        print("client disconnected")


async def broadcast_reload():
    if clients:
        print("Sending reload command to clients")
        #await asyncio.wait([client.send("reload") for client in clients])
        await asyncio.gather(*(client.send("reload") for client in list(clients)), return_exceptions=True)

class LiveReloadHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        if path.endswith(".html") and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            inject = """
            <script>
              const ws = new WebSocket("ws://localhost:5678");
              ws.onmessage = (e) => {
                if (e.data === "reload") location.reload();
              };
            </script>
            """
            content = content.replace("</body>", inject + "</body>")
            encoded = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return None
        return super().send_head()


class ReloadHandler(FileSystemEventHandler):
    def __init__(self, on_reload_callback, loop):
        self.on_reload_callback = on_reload_callback
        self.loop = loop

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith((".html", ".css", ".js")):
            print(f"{event.src_path} modified.")
            outcome = asyncio.run_coroutine_threadsafe(
                self.on_reload_callback(),
                self.loop)
            outcome.add_done_callback(lambda f: f.exception() and print("Error during reload send: ", f.exception()))


def run_http_server():
    httpd = HTTPServer(("localhost", port), LiveReloadHandler)
    httpd.serve_forever()


async def start_server(directory, name):
    loop = asyncio.get_running_loop()

    # Start WebSocket server
    ws_server = await websockets.serve(webocket_handler, "localhost", 5678)
    print("WebSocket server running at ws://localhost:5678")

    # File watcher
    event_handler = ReloadHandler(on_reload_callback=broadcast_reload,
                                  loop=loop)
    observer = Observer()
    observer.schedule(event_handler, path=directory, recursive=True)
    observer.start()

    # Start HTTP server in thread
    def run_http_server():
        httpd = HTTPServer(("localhost", port), LiveReloadHandler)
        url = f"http://localhost:{port}/{name}"
        print(f"Starting server in {directory} : {url}")
        webbrowser.open(url)
        httpd.serve_forever()

    threading.Thread(target=run_http_server, daemon=True).start()

    # Keep the main loop running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        observer.stop()
        observer.join()


def main(directory, name):
    asyncio.run(start_server(directory, name))


def checkDir(directory, fileName="index.html"):
    try:
        os.chdir(directory)
        fileNameSplit = fileName.split(".")
        if fileNameSplit[1] != "html":
            print("Not an HTML file.")
            sys.exit()
        main(directory, fileName)

    except NotADirectoryError:
        directorySplit = directory.split("/")
        fileName = directorySplit[len(directorySplit) - 1]
        removed = directorySplit[:-1]
        joined = "/".join(removed)
        if joined[0] != "/":
            joined = "/" + joined
        checkDir(joined, fileName)

    except FileNotFoundError:
        print("Path is not correct")


if __name__ == "__main__":
    directory = str(sys.argv[1])
    checkDir(directory)
