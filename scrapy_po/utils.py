# -*- coding: utf-8 -*-

def get_callback(request, spider):
    """ Get request.callback of a scrapy.Request, as a callable """
    if request.callback is None:
        return getattr(spider, 'parse')
    return request.callback
