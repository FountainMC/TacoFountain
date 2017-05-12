#!/usr/bin/env bash

function checkDependency {
    dependency="$1"
    if [ -z "$2" ]; then
        dependency_name="$2";
    else
        dependency_name="$dependency";
    fi;
    if ! which "$dependency" >/dev/null 2>&1 ; then
        echo "$dependency_name not found!" >&2;
        echo "Please install $dependency_name to run the TacoFountain build system!" >&2;
        exit 1;
    fi;
}

function downloadPythonDependency {
    package_name="$1"
    package_version="$2"
    if pip show "$package_name" >/dev/null 2>&1; then
        if [ $IGNORE_SYSTEM_PACKAGES ]; then
            echo "Ignoring system package for $package_name" 2>&1;
        else
            return 0 # The dependency was manually installed
        fi;
    fi;
    cache_location="work/python_packages/$package_name/$2"
    if [ ! -d "$cache_location" ]; then
        echo "Python package $package_name not found!" >&2
        echo "Attempting to download from PyPI!" >&2
        python3 scripts/downloadDependency.py "$@" || exit 1
    fi
    PYTHON_DIRS+=("$cache_location")
}

function join_by { local IFS="$1"; shift; echo "$*"; }

checkDependency sha256sum
checkDependency curl
checkDependency python3
checkDependency git
checkDependency java Java
checkDependency mvn Maven

export PYTHON_DIRS=("scripts")

downloadPythonDependency "argh" "0.26.2" "a9b3aaa1904eeb78e32394cd46c6f37ac0fb4af6dc488daa58971bdc7d7fcaf3"

export PYTHONPATH
PYTHONPATH="$(join_by ':' "${PYTHON_DIRS[@]}")"

# We need python 3.6 to run
if  python3 -c 'import sys; exit(sys.version_info >= (3, 6))'; then
    python_version="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')"
    echo "Outdated python version: $python_version" 2>&1
    echo "Python 3.6 is required to run the FountainTaco build system: $python_version" 2>&1
    exit 1
fi

# exec 'yields' execution to the python process
# Instead of spawning a new subprocess, the current process is replaced
# This causes us to exit with their return code, in addition to an insignifigant performance gain
exec python3 -m fountain "$@"
