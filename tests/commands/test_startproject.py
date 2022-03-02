from pathlib import Path
from unittest import mock

from scrapy_poet.commands.startproject import Command, create_package


@mock.patch("scrapy_poet.commands.startproject.create_package")
def test_startproject(mock_create_package, tmpdir):
    project_path = str(tmpdir)

    command = Command()
    command.update_settings = mock.Mock()
    command.poet_pkg_structure(["test_proj", project_path])

    # Simply check if all packages created are all under the project dir
    assert all(
        [
            str(pkg_created.args[0]).startswith(project_path)
            for pkg_created in mock_create_package.call_args_list
        ]
    )

    command.update_settings.assert_called()


def test_startproject_update_settings():
    command = Command()
    mock_settings = mock.MagicMock(Path)
    command.update_settings(mock_settings, "po", "tests.po")

    mock_settings.open.return_value.__enter__.return_value.write.assert_called()


def test_create_package():
    mock_path = mock.Mock()
    create_package(mock_path)

    mock_path.mkdir.assert_called
    mock_path.joinpath.assert_called_with("__init__.py")
