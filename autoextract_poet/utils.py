from dataclasses import dataclass

from autoextract.aio import request_raw

from autoextract_poet.retry import autoextract_retry


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


@dataclass
class QueryLevelError(Exception):

    query: Query
    msg: str


async def request(query: Query):

    async def _request():
        response = await request_raw(query.autoextract_query)[0]
        if "error" in response:
            raise QueryLevelError(query, response)

        return response

    return await autoextract_retry(_request)()
