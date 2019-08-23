# -*- coding: utf-8 -*-
""" Predefined inputs which are possible for page objects """
import attr


@attr.s(auto_attribs=True)
class ResponseData:
    """
    Basic response data: html and url of a web page.
    Response should be downloaded directly (i.e. no browser processing);
    html should be decoded according to page detected encoding.
    """
    url: str
    html: str
