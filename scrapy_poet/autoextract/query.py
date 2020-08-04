from dataclasses import dataclass


@dataclass
class Query:

    url: str
    page_type: str
    # FIXME: is this resource available for everyone?
    # FIXME: decide if this should be True or False by default
    full_html: bool = True

    @property
    def autoextract_query(self):
        return [
            {
                "url": self.url,
                "pageType": self.page_type,
                "fullHtml": self.full_html,
            },
        ]
