# Visage

[![PyPI - Python](https://img.shields.io/pypi/pyversions/Visage.svg?logo=PyPI&label=Python&style=flat-square)](https://pypi.python.org/pypi/Visage/)
[![PyPI - Status](https://img.shields.io/pypi/status/Visage.svg?logo=PyPI&label=Status&style=flat-square)](https://pypi.python.org/pypi/Visage/)
[![PyPI - Version](https://img.shields.io/pypi/v/Visage.svg?logo=PyPI&label=Version&style=flat-square)](https://pypi.python.org/pypi/Visage/)
[![PyPI - License](https://img.shields.io/pypi/l/Visage.svg?logo=PyPI&label=License&style=flat-square)](https://opensource.org/licenses/MIT)

[![Pre-Commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&style=flat-square)](https://github.com/pre-commit/pre-commit)
[![Ruff](https://img.shields.io/badge/ruff-enabled-brightgreen?logo=ruff&style=flat-square)](https://github.com/astral-sh/ruff)

[![Github - Contributors](https://img.shields.io/github/contributors/Buried-In-Code/Visage.svg?logo=Github&label=Contributors&style=flat-square)](https://github.com/Buried-In-Code/Visage/graphs/contributors)
[![Github Action - Testing](https://img.shields.io/github/actions/workflow/status/Buried-In-Code/Visage/testing.yaml?branch=main&logo=Github&label=Testing&style=flat-square)](https://github.com/Buried-In-Code/Visage/actions/workflows/testing.yaml)

Fetches Show, Movie, and Collection cover art from Mediux and updates Plex/Jellyfin using TMDB IDs.

_Jellyfin Collections are not yet supported._

## Installation

### Pipx

1. Ensure you have [Pipx](https://pipx.pypa.io/stable/) installed: `pipx --version`
2. Install the project: `pipx install visage`

## Usage

<details><summary>visage Commands</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run visage --help`](docs/img/visage_commands.svg)

</details>
<details><summary>visage sync</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run visage sync --help`](docs/img/visage_sync.svg)

</details>
<details><summary>visage media</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run visage media --help`](docs/img/visage_media.svg)

</details>
<details><summary>visage set</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run visage set --help`](docs/img/visage_set.svg)

</details>
### Visage settings Commands
<details><summary>visage settings view</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run visage settings view --help`](docs/img/visage_settings_view.svg)

</details>
<details><summary>visage settings locate</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run visage settings locate --help`](docs/img/visage_settings_locate.svg)

</details>

## Notes

- When running a sync/show/collection/movie it will keep downloading sets until all the needed posters are found.
  - **Show:** Poster and Backdrop
  - **Season:** Poster
  - **Episode:** Title Card
  - **Collection:** Poster and Backdrop
  - **Movie:** Poster and Backdrop
- To enable support for Collections in Plex, each Collection needs to have a label with its tmdb-id, in the format of `tmdb-<number>`\
  If using Kometa, refer to [this comment](https://github.com/Buried-In-Code/Visage/issues/12#issuecomment-2622002859) to have Kometa add these labels.

## Settings

To set Plex and/or Jellyfin details, update the file: `~/.config/visage/settings.toml`.
File will be created on first run.

### Example File

```toml
exclude_usernames = []
kometa_integration = false
only_priority_usernames = false
priority_usernames = []

[jellyfin]
base_url = "http://127.0.0.1:8096"
token = "<Token>"

[mediux]
base_url = "https://api.mediux.pro"
token = "<Token>"

[plex]
base_url = "http://127.0.0.1:32400"
token = "<Token>"
```

### Details

- `exclude_usernames`

  A list of usernames whose sets should be ignored when running a sync.

- `kometa_integration`

  If enabled, will remove the `Overlay` label from any media Visage uploads a poster/backdrop/title-card to.

- `only_priority_usernames`

  A boolean flag that limits downloading sets to ones created by the users specified in `priority_usernames`.
  If set to `false`, all sets will be considered unless explicitly excluded in `exclude_usernames`.

- `priority_usernames`

  A list of usernames whose sets should take priority when running a sync.
  If `only_priority_usernames` is set to `true`, only sets from these users will be used.

## Socials

[![Social - Fosstodon](https://img.shields.io/badge/%40BuriedInCode-teal?label=Fosstodon&logo=mastodon&style=for-the-badge)](https://fosstodon.org/@BuriedInCode)\
[![Social - Matrix](https://img.shields.io/matrix/The-Dev-Environment:matrix.org?label=The-Dev-Environment&logo=matrix&style=for-the-badge)](https://matrix.to/#/#The-Dev-Environment:matrix.org)
