# Mediux Posters

[![PyPI - Python](https://img.shields.io/pypi/pyversions/Mediux-Posters.svg?logo=PyPI&label=Python&style=flat-square)](https://pypi.python.org/pypi/Mediux-Posters/)
[![PyPI - Status](https://img.shields.io/pypi/status/Mediux-Posters.svg?logo=PyPI&label=Status&style=flat-square)](https://pypi.python.org/pypi/Mediux-Posters/)
[![PyPI - Version](https://img.shields.io/pypi/v/Mediux-Posters.svg?logo=PyPI&label=Version&style=flat-square)](https://pypi.python.org/pypi/Mediux-Posters/)
[![PyPI - License](https://img.shields.io/pypi/l/Mediux-Posters.svg?logo=PyPI&label=License&style=flat-square)](https://opensource.org/licenses/MIT)

[![prek](https://img.shields.io/badge/prek-enabled-informational?logo=prek&style=flat-square)](https://github.com/j178/prek)
[![Ruff](https://img.shields.io/badge/ruff-enabled-informational?logo=ruff&style=flat-square)](https://github.com/astral-sh/ruff)
[![Ty](https://img.shields.io/badge/ty-enabled-informational?logo=ruff&style=flat-square)](https://github.com/astral-sh/ty)

[![Linting](https://github.com/Buried-In-Code/Mediux-Posters/actions/workflows/linting.yaml/badge.svg)](https://github.com/Buried-In-Code/Mediux-Posters/actions/workflows/linting.yaml)
[![Testing](https://github.com/Buried-In-Code/Mediux-Posters/actions/workflows/testing.yaml/badge.svg)](https://github.com/Buried-In-Code/Mediux-Posters/actions/workflows/testing.yaml)
[![Publishing](https://github.com/Buried-In-Code/Mediux-Posters/actions/workflows/publishing.yaml/badge.svg)](https://github.com/Buried-In-Code/Mediux-Posters/actions/workflows/publishing.yaml)

Fetches Show, Movie, and Collection cover art from Mediux and updates Plex/Jellyfin using TMDB IDs.

_Jellyfin Collections are not yet supported._

## Installation

### Pipx

1. Ensure you have [Pipx](https://pipx.pypa.io/stable/) installed: `pipx --version`
2. Install the project: `pipx install Mediux-Posters`

## Usage

<details><summary>mediux-posters Commands</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run mediux-posters`](docs/img/mediux-posters.svg)

</details>
<details><summary>mediux-posters sync</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run mediux-posters sync --help`](docs/img/mediux-posters_sync.svg)

</details>
<details><summary>mediux-posters media</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run mediux-posters media --help`](docs/img/mediux-posters_media.svg)

</details>
<details><summary>mediux-posters set</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run mediux-posters set --help`](docs/img/mediux-posters_set.svg)

</details>
<details><summary>mediux-posters settings</summary>

  <!-- RICH-CODEX hide_command: true -->
  ![`uv run mediux-posters settings --help`](docs/img/mediux-posters_settings.svg)

</details>

## Notes

- When running a sync/show/collection/movie it will keep downloading sets until all the needed posters are found.
  - **Show, Collection, Movie:** Poster, Backdrop, Logo (and Album/SquareArt only on Plex)
  - **Season:** Poster, Backdrop
  - **Episode:** TitleCard, Backdrop
- To enable support for Collections in Plex, each Collection needs to have a label with its tmdb-id, in the format of `tmdb-<number>`\
  If using Kometa, refer to [this comment](https://github.com/Buried-In-Code/Mediux-Posters/issues/12#issuecomment-2622002859) to have Kometa add these labels.

## Settings

To set Plex and/or Jellyfin details, update the file: `~/.config/mediux-posters/settings.toml`.
File will be created on first run.

### Example File

```toml
exclude_usernames = []
kometa_integration = false
only_priority_usernames = false
priority_usernames = []

[covers]
path = "~/.cache/mediux-posters/covers"
store = true

[jellyfin]
base_url = "http://127.0.0.1:8096"
token = "<Token>"

[mediux]
base_url = "https://images.mediux.io"
token = "<Token>"

[plex]
base_url = "http://127.0.0.1:32400"
token = "<Token>"
```

### Details

- `covers.path`

  Folder location as to where to store downloaded covers.

- `covers.store`

  Wether to store the images in the cache between runs, useful when running multiple services to not have to redownload images.

- `exclude_usernames`

  A list of usernames whose sets should be ignored when running a sync.

- `kometa_integration`

  If enabled, will remove the `Overlay` label from any media Mediux-Posters uploads a poster/backdrop/title-card to.

- `only_priority_usernames`

  A boolean flag that limits downloading sets to ones created by the users specified in `priority_usernames`.
  If set to `false`, all sets will be considered unless explicitly excluded in `exclude_usernames`.

- `priority_usernames`

  A list of usernames whose sets should take priority when running a sync.
  If `only_priority_usernames` is set to `true`, only sets from these users will be used.

## Socials

[![Social - Fosstodon](https://img.shields.io/badge/%40BuriedInCode-teal?label=Fosstodon&logo=mastodon&style=for-the-badge)](https://fosstodon.org/@BuriedInCode)\
[![Social - Matrix](https://img.shields.io/matrix/The-Dev-Environment:matrix.org?label=The-Dev-Environment&logo=matrix&style=for-the-badge)](https://matrix.to/#/#The-Dev-Environment:matrix.org)
