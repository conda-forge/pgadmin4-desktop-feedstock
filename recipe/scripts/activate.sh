#!/bin/bash

if [[ -n "$PGADMIN4_PY_HOME" ]]; then
  export _CONDA_SET_PGADMIN4_PY_EXEC="$PGADMIN4_PY_EXEC"
  export _CONDA_SET_PGADMIN4_PY_HOME="$PGADMIN4_PY_HOME"
fi

pushd "$CONDA_PREFIX"
  _PGADMIN4_PY_LIB=`bin/python -c "import pgadmin4, os; print(os.path.dirname(pgadmin4.__file__))" | tail -n 1`
  export PGADMIN4_PY_EXEC="bin/python"
  export PGADMIN4_PY_HOME="${_PGADMIN4_PY_LIB}/pgAdmin4.py"
popd

# Special app link for MacOS
if [[ "$OSTYPE" == "darwin"* ]]; then
  WEB_PATH="$CONDA_PREFIX/usr/pgadmin4.app/Contents/Resources/web"
  BACKUP_PATH="$CONDA_PREFIX/usr/pgadmin4.app/Contents/Resources/_conda_set_web"
  if [[ -e "$WEB_PATH" || -L "$WEB_PATH" ]]; then
    rm -rf "$BACKUP_PATH"
    mv "$WEB_PATH" "$BACKUP_PATH"
  fi
  ln -s "$CONDA_PREFIX/$_PGADMIN4_PY_LIB" "$WEB_PATH"
fi
