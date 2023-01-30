import argparse
import socket
import sys
import time
from importlib import import_module
from subprocess import PIPE, Popen

from twisted.internet import reactor
from twisted.web.server import Site


def get_ephemeral_port():
    s = socket.socket()
    s.bind(("", 0))
    return s.getsockname()[1]


class MockServer:
    def __init__(self, resource, port=None):
        self.resource = "{0}.{1}".format(resource.__module__, resource.__name__)
        self.proc = None
        host = socket.gethostbyname(socket.gethostname())
        self.port = port or get_ephemeral_port()
        self.root_url = "http://%s:%d" % (host, self.port)

    def __enter__(self):
        self.proc = Popen(
            [
                sys.executable,
                "-u",
                "-m",
                "scrapy_poet.utils.mockserver",
                self.resource,
                "--port",
                str(self.port),
            ],
            stdout=PIPE,
        )
        self.proc.stdout.readline()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.proc.kill()
        self.proc.wait()
        time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("resource")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    module_name, name = args.resource.rsplit(".", 1)
    sys.path.append(".")
    resource = getattr(import_module(module_name), name)()
    http_port = reactor.listenTCP(args.port, Site(resource))

    def print_listening():
        host = http_port.getHost()
        print(
            "Mock server {0} running at http://{1}:{2}".format(
                resource, host.host, host.port
            )
        )

    reactor.callWhenRunning(print_listening)
    reactor.run()


if __name__ == "__main__":
    main()
