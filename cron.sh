#!/usr/bin/env bash

VENV_DIR="venv"

if [ ! -d "${VENV_DIR}" ]; then
  virtualenv "${VENV_DIR}"
  if [ "$?" -ne 0 ]; then
    echo "failed to create virtual environment for python executable."
    exit 1
  fi
fi
eval "source ${VENV_DIR}/bin/activate"
pip install -r requirements.txt

python backup.py

if [ "$?" -ne 0 ]; then
  echo "failure: unable to backup hackfoldrs."
  exit 1
fi
eval "deactivate"
