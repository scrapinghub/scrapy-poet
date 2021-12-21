from unittest import mock
from pathlib import PosixPath

from scrapy_poet.utils import get_scrapy_data_path


@mock.patch("scrapy_poet.utils.os.makedirs")
@mock.patch("scrapy_poet.utils.inside_project")
def test_get_scrapy_data_path(mock_inside_project, mock_makedirs, tmp_path):
    mock_inside_project.return_value = False

    path = tmp_path / "test_dir"
    result = get_scrapy_data_path(createdir=True, default_dir=path)

    assert isinstance(result, PosixPath)
    assert str(result)  # should be non-empty

    mock_inside_project.assert_called_once()

    mock_makedirs.assert_called_once()
    mock_makedirs.assert_called_with(path, exist_ok=True)
