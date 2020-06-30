from autoextract.aio import request_raw

from autoextract_poet.query import Query
from autoextract_poet.retry import autoextract_retry
from autoextract_poet.exceptions import QueryLevelError


async def request(query: Query):

    async def _request():
        response = await request_raw(query.autoextract_query)[0]
        if "error" in response:
            raise QueryLevelError(query, response)

        return response

    return await autoextract_retry(_request)()
