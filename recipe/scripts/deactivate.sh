if [[ "${_CONDA_SET_PGADMIN4_PY_HOME+x}" ]] ; then
  export PGADMIN4_PY_HOME=$_CONDA_SET_PGADMIN4_PY_HOME
  export PGADMIN4_PY_EXEC=$_CONDA_SET_PGADMIN4_PY_EXEC
  unset _CONDA_SET_PGADMIN4_PY_EXEC
  unset _CONDA_SET_PGADMIN4_PY_HOME
fi

WEB_PATH="$CONDA_PREFIX/usr/pgadmin4.app/Contents/Resources/web"
BACKUP_PATH="$CONDA_PREFIX/usr/pgadmin4.app/Contents/Resources/_conda_set_web"
if [[ -e "$WEB_PATH" || -L "$WEB_PATH" ]]; then
  rm -rf "$WEB_PATH"
fi
if [[ -e "$BACKUP_PATH" || -L "$BACKUP_PATH" ]]; then
  mv "$BACKUP_PATH" "$WEB_PATH"
fi
