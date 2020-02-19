# -*- coding: utf-8 -*-
""" Customizations allows to choose the right PageObject based on the response """
import abc
from scrapy import Request, Spider
from scrapy.http import Response

from typing import Type, Mapping


class Customizations:

    def __init__(self, crawler, *args, **kwargs):
        pass

    @abc.abstractmethod
    def __call__(self, request: Request, response: Response,
                 spider: Spider, cls: Type) -> Type:
        pass


class IdentityCustomizations(Customizations):

    def __call__(self, request: Request, response: Response,
                 spider: Spider, cls: Type) -> Type:
        return cls