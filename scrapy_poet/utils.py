import os

from scrapy.utils.project import project_data_dir, inside_project


def get_scrapy_data_path(createdir=True):
    """ Return a path to a folder where Scrapy is storing data.
    Usually that's a .scrapy folder inside the project.
    """
    # This code is extracted from scrapy.utils.project.data_path function,
    # which does too many things.
    path = project_data_dir() if inside_project() else ".scrapy"
    if createdir:
        os.makedirs(path, exist_ok=True)
    return path
