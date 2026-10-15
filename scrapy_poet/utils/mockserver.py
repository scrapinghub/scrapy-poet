from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from importlib import import_module
from subprocess import PIPE, Popen
from typing import TYPE_CHECKING

from twisted.web.server import Site

if TYPE_CHECKING:
    from types import TracebackType
    from typing import Self

    from twisted.web.resource import Resource


def get_ephemeral_port() -> int:
    s = socket.socket()
    s.bind(("", 0))
    port: int = s.getsockname()[1]
    return port


class MockServer:
    def __init__(
        self,
        resource: type[Resource],
        port: int | None = None,
        pythonpath: str | None = None,
    ) -> None:
        self.resource = f"{resource.__module__}.{resource.__name__}"
        self.proc: Popen[bytes] | None = None
        host = socket.gethostbyname(socket.gethostname())
        self.port = port or get_ephemeral_port()
        self.root_url = f"http://{host}:{self.port}"
        self.pythonpath = pythonpath or ""

    def __enter__(self) -> Self:
        self.proc = Popen(  # noqa: S603
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
            env={**os.environ, "PYTHONPATH": self.pythonpath},
        )
        assert self.proc.stdout
        self.proc.stdout.readline()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self.proc
        self.proc.terminate()
        self.proc.wait()
        time.sleep(0.2)


def main() -> None:
    from twisted.internet import reactor

    parser = argparse.ArgumentParser()
    parser.add_argument("resource")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    module_name, name = args.resource.rsplit(".", 1)
    sys.path.append(".")
    resource = getattr(import_module(module_name), name)()
    http_port = reactor.listenTCP(args.port, Site(resource))  # type: ignore[arg-type]

    def print_listening() -> None:
        host = http_port.getHost()  # type: ignore[misc]
        print(f"Mock server {resource} running at http://{host.host}:{host.port}")

    reactor.callWhenRunning(print_listening)
    reactor.run()  # type: ignore[misc]


if __name__ == "__main__":
    main()
