from dataclasses import dataclass


@dataclass
class Query:

    url: str
    page_type: str
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
