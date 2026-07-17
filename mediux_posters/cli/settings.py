__all__ = ["register"]

from argparse import _SubParsersAction

from rich_argparse import HelpPreviewAction, RichHelpFormatter

from mediux_posters.settings import Settings


def register(subparsers: _SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "settings", help="Display app settings and defaults.", formatter_class=RichHelpFormatter
    )
    parser.add_argument(
        "--generate-help-preview",
        action=HelpPreviewAction,
        path="docs/img/mediux-posters_settings.svg",
    )
    parser.set_defaults(func=run)


def run(args) -> None:  # noqa: ANN001, ARG001
    settings = Settings.load()
    settings.display()
