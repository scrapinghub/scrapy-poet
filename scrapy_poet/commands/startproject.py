from textwrap import dedent

from pathlib import Path

from scrapy.commands import startproject


class Command(startproject.Command):
    """
    Invokes the regular scrapy startproject command, but also initializes some packages
    and settings required by scrapy-poet
    """

    def run(self, args, opts):
        super(Command, self).run(args, opts)
        if self.exitcode:
            return

        project_name = args[0]
        project_dir = args[0]

        if len(args) == 2:
            project_dir = args[1]

        project_path = Path(project_dir)
        po_package = f"{project_name}.po"
        po_tests_package = f"tests.po"
        po_path = project_path / project_name / "po"
        po_tests_path = project_path / "tests" / "po"
        po_tests_path_fixtures = project_path / "tests" / "po" / "fixtures"
        po_templates_path = po_path / "templates"

        for path in (po_path, po_tests_path, po_templates_path):
            create_package(path)
        po_tests_path_fixtures.mkdir(parents=True, exist_ok=True)

        settings_path = project_path / project_name / "settings.py"
        with settings_path.open("a") as f:
            f.write(scrapy_poet_settings(po_package, po_tests_package))


def scrapy_poet_settings(po_package: str, po_tests_package) -> str:
    return dedent(
        f"""
        
        # Scrapy-poet settings
        
        DOWNLOADER_MIDDLEWARES = {{
           'scrapy_poet.InjectionMiddleware': 543,
        }}
        
        PO_PACKAGE = "{po_package}"
        PO_TESTS_PACKAGE = "{po_tests_package}"
        
        from web_poet.overrides import find_page_object_overrides
        SCRAPY_POET_OVERRIDES = find_page_object_overrides(PO_PACKAGE)        
        """)


def create_package(path: Path):
    path.mkdir(parents=True, exist_ok=True)
    path.joinpath("__init__.py").touch(exist_ok=True)


