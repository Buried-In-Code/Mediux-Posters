__all__ = ["build_parser"]

from argparse import ArgumentParser

from rich_argparse import HelpPreviewAction, RichHelpFormatter

from mediux_posters import __version__
from mediux_posters.cli.media import register as register_media
from mediux_posters.cli.set import register as register_set
from mediux_posters.cli.settings import register as register_settings
from mediux_posters.cli.sync import register as register_sync


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(prog="mediux-posters", formatter_class=RichHelpFormatter)
    parser.add_argument("--version", action="version", version=f"Mediux Posters v{__version__}")
    parser.add_argument(
        "--generate-help-preview", action=HelpPreviewAction, path="docs/img/mediux-posters.svg"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    register_media(subparsers=subparsers)
    register_set(subparsers=subparsers)
    register_settings(subparsers=subparsers)
    register_sync(subparsers=subparsers)

    return parser
