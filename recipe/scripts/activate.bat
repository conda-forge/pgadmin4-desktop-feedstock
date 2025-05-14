if defined PGADMIN4_PY_HOME (
    set "_CONDA_SET_PGADMIN4_PY_HOME=%PGADMIN4_PY_HOME%"
    set "_CONDA_SET_PGADMIN4_PY_EXEC=%PGADMIN4_PY_EXEC%"
)

dir "%CONDA_PREFIX%\lib\site-packages\pgadmin4" >nul 2>&1 || (
    echo "pgadmin4 package not found in %CONDA_PREFIX%\lib\site-packages\pgadmin4"
    exit /b 1
)
dir "%CONDA_PREFIX%\bin\python.exe" >nul 2>&1 || (
    echo "python.exe not found in %CONDA_PREFIX%\bin\python.exe"
    exit /b 1
)

set "PGADMIN4_PY_EXEC=%CONDA_PREFIX%\bin\python.exe"
set "PGADMIN4_PY_HOME=%CONDA_PREFIX%\lib\site-packages\pgadmin4\pgAdmin4.py"
