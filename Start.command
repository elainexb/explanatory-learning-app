#!/bin/bash
cd -- "$(dirname -- "$0")" || exit 1
runtime="/usr/local/bin/python3"
if [ ! -x "$runtime" ]; then
  runtime="$(command -v python3)"
fi
if [ -z "$runtime" ]; then
  echo 'Python was not found. Ask the maintainer to check this computer’s runtime.'
  read -r -p 'Press Enter to close'
  exit 1
fi
"$runtime" server.py "$@"
result=$?
if [ "$result" -ne 0 ]; then
  read -r -p 'Startup failed. Press Enter to close'
fi
