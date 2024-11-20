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

## Installation

### Pipx _(Not Yet Implemented)_

1. Ensure you have [Pipx](https://pipxproject.github.io/pipx/) installed: `pipx --version`
2. Install the project: `pipx install Mediux-Posters`

### From Source

1. Ensure you have a supported version of [Python](https://www.python.org/) installed: `python --version`
2. Clone the repository: `git clone https://github.com/Buried-In-Code/Mediux-Posters`
3. Install the project: `pip install .`

## Usage

<details><summary>Mediux-Posters commands</summary>

  ![`uv run Mediux-Posters --help`](docs/img/usage-01.svg)

</details>
<details><summary>Mediux-Posters Plex commands</summary>

  ![`uv run Mediux-Posters plex --help`](docs/img/usage-plex-01.svg)

</details>
<details><summary>Mediux-Posters Plex sync command</summary>

  ![`uv run Mediux-Posters plex sync --help`](docs/img/usage-plex-02.svg)

</details>
<details><summary>Mediux-Posters Plex set command</summary>

  ![`uv run Mediux-Posters plex set --help`](docs/img/usage-plex-03.svg)

</details>
<details><summary>Mediux-Posters Jellyfin commands</summary>

  ![`uv run Mediux-Posters jellyfin --help`](docs/img/usage-jellyfin-01.svg)

</details>
<details><summary>Mediux-Posters Jellyfin sync commands</summary>

  ![`uv run Mediux-Posters jellyfin sync --help`](docs/img/usage-jellyfin-02.svg)

</details>

## Settings

To set Plex and/or Jellyfin details, update the file: `~/.config/mediux-posters/settings.toml`.
File will be created on first run.

### Example File

```toml
[jellyfin]
base_url = "http://127.0.0.1:8096"
api_key = "<API Key>"

[plex]
base_url = "http://127.0.0.1:32400"
token = "<Token>"
```

## Socials

[![Social - Fosstodon](https://img.shields.io/badge/%40BuriedInCode-teal?label=Fosstodon&logo=mastodon&style=for-the-badge)](https://fosstodon.org/@BuriedInCode)\
[![Social - Matrix](https://img.shields.io/matrix/The-Dev-Environment:matrix.org?label=The-Dev-Environment&logo=matrix&style=for-the-badge)](https://matrix.to/#/#The-Dev-Environment:matrix.org)
