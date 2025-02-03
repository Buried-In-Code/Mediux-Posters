# Mediux Posters

[![PyPI - Python](https://img.shields.io/pypi/pyversions/Mediux-Posters.svg?logo=PyPI&label=Python&style=flat-square)](https://pypi.python.org/pypi/Mediux-Posters/)
[![PyPI - Status](https://img.shields.io/pypi/status/Mediux-Posters.svg?logo=PyPI&label=Status&style=flat-square)](https://pypi.python.org/pypi/Mediux-Posters/)
[![PyPI - Version](https://img.shields.io/pypi/v/Mediux-Posters.svg?logo=PyPI&label=Version&style=flat-square)](https://pypi.python.org/pypi/Mediux-Posters/)
[![PyPI - License](https://img.shields.io/pypi/l/Mediux-Posters.svg?logo=PyPI&label=License&style=flat-square)](https://opensource.org/licenses/MIT)

[![Pre-Commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&style=flat-square)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/badge/ruff-enabled-brightgreen?logo=ruff&style=flat-square)](https://github.com/astral-sh/ruff)

[![Github - Contributors](https://img.shields.io/github/contributors/Buried-In-Code/Mediux-Posters.svg?logo=Github&label=Contributors&style=flat-square)](https://github.com/Buried-In-Code/Mediux-Posters/graphs/contributors)

Pull Shows, Movies and Collections from Mediux and updates Plex/Jellyfin.
Pulls Posters, Backdrops and Title Cards.

**_Uses TMDB Id to match shows/movies/collections_**

## Installation

### Pipx

1. Ensure you have [Pipx](https://pipx.pypa.io/stable/) installed: `pipx --version`
2. Install the project: `pipx install Mediux-Posters`

## Usage

<details><summary>Mediux-Posters Commands</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters --help`](docs/img/mediux-posters_commands.svg)

</details>
<details><summary>Mediux-Posters sync</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters sync --help`](docs/img/mediux-posters_sync.svg)

</details>
<details><summary>Mediux-Posters set</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters set --help`](docs/img/mediux-posters_set.svg)

</details>
<details><summary>Mediux-Posters show</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters show --help`](docs/img/mediux-posters_show.svg)

</details>
<details><summary>Mediux-Posters collection</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters collection --help`](docs/img/mediux-posters_collection.svg)

</details>
<details><summary>Mediux-Posters movie</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters movie --help`](docs/img/mediux-posters_movie.svg)

</details>
<details><summary>Mediux-Posters settings</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run Mediux-Posters settings --help`](docs/img/mediux-posters_settings.svg)

</details>


## Settings

To set Plex and/or Jellyfin details, update the file: `~/.config/mediux-posters/settings.toml`.
File will be created on first run.

### Example File

```toml
exclude_usernames = []
only_priority_usernames = false
priority_usernames = []

[jellyfin]
base_url = "http://127.0.0.1:8096"
token = "<Token>"

[plex]
base_url = "http://127.0.0.1:32400"
token = "<Token>"
```

### Details

- `exclude_usernames`

  A list of usernames whose sets should be ignored when running a sync.

- `only_priority_usernames`

  A boolean flag that limits downloading sets to ones created by the users specified in `priority_usernames`.
  If set to `false`, all sets will be considered unless explicitly excluded in `exclude_usernames`.

- `priority_usernames`

  A list of usernames whose sets should take priority when running a sync.
  If `only_priority_usernames` is set to `true`, only sets from these users will be used.

## Socials

[![Social - Fosstodon](https://img.shields.io/badge/%40BuriedInCode-teal?label=Fosstodon&logo=mastodon&style=for-the-badge)](https://fosstodon.org/@BuriedInCode)\
[![Social - Matrix](https://img.shields.io/matrix/The-Dev-Environment:matrix.org?label=The-Dev-Environment&logo=matrix&style=for-the-badge)](https://matrix.to/#/#The-Dev-Environment:matrix.org)
