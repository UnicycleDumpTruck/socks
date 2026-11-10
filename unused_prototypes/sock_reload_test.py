import random
import threading
from time import sleep
from nicegui import ui

#container = ui.column()

jobs = []

@ui.refreshable
def jobs_ui() -> None:
    ui.html(', '.join(str(n) for n in sorted(jobs)))

def add_job() -> None:
    jobs.append(random.randint(0,100))
    jobs_ui.refresh()

#thread = threading.Thread(target=add_job, daemon=False)
#thread.start()

#with container:
#ui.html("First line")
#ui.add_body_html("how about this")

jobs_ui()
ui.button('Add job', on_click=add_job)

ui.run(show=False)
