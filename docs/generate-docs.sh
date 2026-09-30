#!/usr/bin/env bash

COLUMNS=120 pdm run mediux-posters --generate-help-preview
COLUMNS=120 pdm run mediux-posters media --generate-help-preview
COLUMNS=120 pdm run mediux-posters set --generate-help-preview
COLUMNS=120 pdm run mediux-posters settings --generate-help-preview
COLUMNS=120 pdm run mediux-posters sync --generate-help-preview
