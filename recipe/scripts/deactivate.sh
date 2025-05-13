if [[ "${_CONDA_SET_PGADMIN4_PY_HOME+x}" ]] ; then
  export PGADMIN4_PY_HOME=$_CONDA_SET_PGADMIN4_PY_HOME
  export PGADMIN4_PY_EXEC=$_CONDA_SET_PGADMIN4_PY_EXEC
  unset _CONDA_SET_PGADMIN4_PY_EXEC
  unset _CONDA_SET_PGADMIN4_PY_HOME
fi

if [[ -L "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/_conda_set_web ]]; then
  rm "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/web
  mv "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/_conda_set_web "$CONDA_PREFIX"/usr/pgadmin4.app/Contents/Resources/web
fi
