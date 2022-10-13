"""
This package is just for overrides testing purposes.
"""
import socket

from url_matcher.util import get_domain

from tests.mockserver import get_ephemeral_port

# Need to define it here since it's always changing
DOMAIN = get_domain(socket.gethostbyname(socket.gethostname()))
PORT = get_ephemeral_port()
URL = f"{DOMAIN}:{PORT}"
