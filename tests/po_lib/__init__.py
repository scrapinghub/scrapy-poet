"""
This package is just for overrides testing purposes.
"""
import socket

from url_matcher.util import get_domain
from web_poet import ItemWebPage, handle_urls

from tests.mockserver import get_ephemeral_port

# Need to define it here since it's always changing
DOMAIN = get_domain(socket.gethostbyname(socket.gethostname()))
PORT = get_ephemeral_port()


class POOverriden(ItemWebPage):
    def to_item(self):
        return {"msg": "PO that will be replace"}


@handle_urls(f"{DOMAIN}:{PORT}", overrides=POOverriden)
class POIntegration(ItemWebPage):
    def to_item(self):
        return {"msg": "PO replacement"}
