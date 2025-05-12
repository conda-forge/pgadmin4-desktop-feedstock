#!/bin/bash

if [[ -n "$PGADMIN4_PY_HOME" ]]; then
    export _CONDA_SET_PGADMIN4_PY_HOME=$PGADMIN4_PY_HOME
fi
export PGADMIN4_PY_HOME=`$CONDA_PREFIX/bin/python -c "import pgadmin4, os; print(os.path.dirname(pgadmin4.__file__))" | tail -n 1`/pgAdmin4.py
