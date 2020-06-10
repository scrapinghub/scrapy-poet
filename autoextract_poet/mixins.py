from web_poet.mixins import ResponseShortcutsMixin
from web_poet.page_inputs import ResponseData


class ResponseShortcutsMixin(ResponseShortcutsMixin):

    @property
    def response(self):
        # FIXME: raise a custom Exception or create a separate method for errors
        data = self.autoextract_response.data

        # FIXME: pageType could be different to item key in the response
        pageType = data["query"]["userQuery"]["pageType"]

        # FIXME: maybe better to have a AEResponseData to not confuse with the ResponseData semantic
        return ResponseData(
            url=data[pageType].get("url", data["query"]["userQuery"]["url"]),
            html=self.autoextract_response.data.get("html", ""),
        )
