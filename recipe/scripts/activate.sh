#!/bin/bash

if [[ -n "$PGADMIN4_PY_HOME" ]]; then
  export _CONDA_SET_PGADMIN4_PY_EXEC="$PGADMIN4_PY_EXEC"
  export _CONDA_SET_PGADMIN4_PY_HOME="$PGADMIN4_PY_HOME"
fi
export PGADMIN4_PY_EXEC="$CONDA_PREFIX"/bin/python
export PGADMIN4_PY_HOME=`$CONDA_PREFIX/bin/python -c "import pgadmin4, os; print(os.path.dirname(pgadmin4.__file__))" | tail -n 1`/pgAdmin4.py

# Special app link for MacOS
if [[ "$OSTYPE" == "darwin"* ]]; then
  if [[ -e "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/web ]]; then
    mv "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/web "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/_conda_set_web
  fi
  ln -s "$PGADMIN4_PY_HOME" "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/web
  ls -lrt "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/web
fi