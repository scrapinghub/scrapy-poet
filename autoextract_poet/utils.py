from autoextract.aio import request_raw
from autocrawl.autoextract_retry import autoextract_retry

from autoextract_poet.exceptions import QueryLevelError


async def request(url: str, page_type: str, full_html=True):
    query = [dict(url=url, pageType=page_type, fullHtml=full_html)]

    async def _request():
        response_per_url = await request_raw(query)

        # A single url send, so a single element in the response
        response = response_per_url[0]

        if "error" in response:
            raise QueryLevelError(query, response)

        return response

    return await autoextract_retry(_request)()
