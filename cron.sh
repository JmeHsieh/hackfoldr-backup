#!/usr/bin/env bash

VENV_DIR="venv"
SSH_KEY_FILE="${HOME}/.ssh/id_rsa"

if [ ! -d "${VENV_DIR}" ]; then
  virtualenv "${VENV_DIR}"
  if [ "$?" -ne 0 ]; then
    echo "failed to create virtual environment for python executable."
    exit 1
  fi
fi
eval "source ${VENV_DIR}/bin/activate"
pip install -r requirements.txt

# make sure no passphrase set on ${SSH_KEY_FILE}
# install `keychain` otherwise.
export GIT_SSH_COMMAND="ssh -i ${SSH_KEY_FILE}"
python backup.py

if [ "$?" -ne 0 ]; then
  echo "failure: unable to generate repo info."
  exit 1
fi
eval "deactivate"
