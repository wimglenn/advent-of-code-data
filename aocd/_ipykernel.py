import os
import re

import urllib3

_IPYNB_PATTERN = re.compile(r"(?<=kernel-)[\w\-]+(?=\.json)")

def get_ipynb_path() -> str:
    # helper function so that "from aocd import data" can introspect the year/day from
    # the .ipynb filename. inline imports to avoid hard-dependency on IPython/jupyter
    import IPython
    from jupyter_server import serverapp
    from jupyter_server.utils import url_path_join

    ipython = IPython.get_ipython() # type: ignore[attr-defined] # IPython doesn't explicitly export the get_ipython function
    app = ipython.config["IPKernelApp"]
    match = _IPYNB_PATTERN.search(app["connection_file"])
    assert match is not None
    kernel_id = match[0]
    http = urllib3.PoolManager()
    for serv in serverapp.list_running_servers(): # type: ignore[no-untyped-call] # jupyter doesn't provide type hints for list_running_servers
        url = url_path_join(serv["url"], "api/sessions") # type: ignore[no-untyped-call] # jupyter doesn't provide type hints for url_path_join
        resp = http.request("GET", url, fields={"token": serv["token"]})
        if resp.status >= 400:
            raise urllib3.exceptions.ResponseError(f"Bad HTTP response status ({resp.status})")
        for sess in resp.json():
            if kernel_id == sess["kernel"]["id"]:
                path = serv["root_dir"]
                assert isinstance(path, str)
                fname = sess["notebook"]["path"]
                assert isinstance(fname, str)
                return os.path.join(path, fname)
    assert False, "unreachable"
