#!/usr/bin/env bash
set -eux

if [[ "${OSTYPE}" == "linux"* ]] || [[ "${OSTYPE}" == "darwin"* ]]; then
  export PG_YARN=${BUILD_PREFIX}/bin/yarn
else
  export PG_YARN=${BUILD_PREFIX}/Library/bin/yarn
fi

source "${RECIPE_DIR}"/building/build-functions.sh

_setup_env "${SRC_DIR}"
_cleanup
_setup_dirs
_install_electron
_build_runtime
_install_icons_menu
_install_bundle
_generate_sbom

for CHANGE in "activate" "deactivate"
do
    mkdir -p "${PREFIX}/etc/conda/${CHANGE}.d"
    if [[ "${OSTYPE}" == "linux"* ]] || [[ "${OSTYPE}" == "darwin"* ]]; then
      cp "${RECIPE_DIR}/scripts/${CHANGE}.sh" "${PREFIX}/etc/conda/${CHANGE}.d/${PKG_NAME}_${CHANGE}.sh"
    else
      cp "${RECIPE_DIR}/scripts/${CHANGE}.bat" "${PREFIX}/etc/conda/${CHANGE}.d/${PKG_NAME}_${CHANGE}.bat"
    fi
done
