from textwrap import dedent
from pathlib import Path
from typing import List

from scrapy.commands import startproject


class Command(startproject.Command):
    """
    Invokes the regular `scrapy startproject` command, but also initializes some
    packages and settings required by scrapy-poet.
    """

    def run(self, args: List[str], opts) -> None:
        super(Command, self).run(args, opts)
        if self.exitcode:
            return

        self.poet_pkg_structure(args)

    def poet_pkg_structure(self, args: List[str]) -> None:
        project_name = args[0]
        project_dir = args[0]

        if len(args) == 2:
            project_dir = args[1]

        project_path = Path(project_dir)
        po_package = f"{project_name}.po"
        po_tests_package = "tests.po"

        po_path = project_path / project_name / "po"
        po_templates_path = po_path / "templates"
        po_tests_path = project_path / "tests" / "po"
        po_tests_path_fixtures = project_path / "tests" / "po" / "fixtures"
        for path in (po_path, po_templates_path, po_tests_path, po_tests_path_fixtures):
            create_package(path)

        settings = project_path / project_name / "settings.py"
        self.update_settings(settings, po_package, po_tests_package)

    def update_settings(self, settings, po_package, po_tests_package):
        with settings.open("a") as f:
            f.write(scrapy_poet_settings(po_package, po_tests_package))


def scrapy_poet_settings(po_package: str, po_tests_package: str) -> str:
    return dedent(  # pragma: no cover
        f"""
        # Scrapy-poet settings

        DOWNLOADER_MIDDLEWARES = {{
           'scrapy_poet.InjectionMiddleware': 543,
        }}

        PO_PACKAGE = "{po_package}"
        PO_TESTS_PACKAGE = "{po_tests_package}"

        from web_poet import default_registry
        SCRAPY_POET_OVERRIDES = default_registry.get_overrides(filters=PO_PACKAGE)
        """
    )


def create_package(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("__init__.py").touch(exist_ok=True)
