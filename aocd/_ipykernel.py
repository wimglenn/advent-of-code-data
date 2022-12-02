import os
import re

import requests


def get_ipynb_path():
    # inline imports to avoid hard-dependency on IPython/jupyter
    import IPython
    from jupyter_server import serverapp
    from jupyter_server.utils import url_path_join
    app = IPython.get_ipython().config["IPKernelApp"]
    kernel_id = re.search(r"(?<=kernel-)[\w\-]+(?=\.json)", app["connection_file"])[0]
    for serv in serverapp.list_running_servers():
        url = url_path_join(serv["url"], "api/sessions")
        resp = requests.get(url, params={"token": serv["token"]})
        resp.raise_for_status()
        for sess in resp.json():
            if kernel_id == sess["kernel"]["id"]:
                path = serv["root_dir"]
                fname = sess["notebook"]["path"]
                return os.path.join(path, fname)
