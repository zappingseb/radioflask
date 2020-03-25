"""
The Flask app

Please read carefully AUTOSTART AND PORT 80.

System settings need to be made to this app on startup
"""

# --------------- AUTOSTART APP ------------------------
# To start globally in rc.local, this path needs to be added
# Add:
# python3 /home/pi/share/radioflask/__init__.py >> /home/pi/share/all_log.txt &
#
# to /etc/rc.local
#
import sys
sys.path.append('/home/pi/.local/lib/python3.7/site-packages')

from views import app, csrf
from os import path, walk

extra_dirs = ['./templates', './static']
extra_files = extra_dirs[:]
for extra_dir in extra_dirs:
    for dirname, dirs, files in walk(extra_dir):
        for filename in files:
            filename = path.join(dirname, filename)
            if path.isfile(filename):
                extra_files.append(filename)

app.config.update(TEMPLATES_AUTO_RELOAD=True)
csrf.init_app(app)

# ---------- PORT 80 App ---------------------
# need sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3.7
app.run(extra_files=extra_files, port=80, host='0.0.0.0')


