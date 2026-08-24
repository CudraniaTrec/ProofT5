#!/usr/bin/env bash

PROOFT5_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export PROOFT5_ROOT
export PROOFT5_JAVA_HOME="${PROOFT5_JAVA_HOME:-/data2/x/hzc/.local/jdks/temurin17}"
export PROOFT5_JAVA="${PROOFT5_JAVA:-${PROOFT5_JAVA_HOME}/bin/java}"
export PROOFT5_JAVAC="${PROOFT5_JAVAC:-${PROOFT5_JAVA_HOME}/bin/javac}"
export PROOFT5_SUFU_PARSER="${PROOFT5_SUFU_PARSER:-${PROOFT5_ROOT}/SuFu/SuFu/surface/f}"
export PROOFT5_SUFU_EXECUTOR="${PROOFT5_SUFU_EXECUTOR:-${PROOFT5_SUFU_PARSER}}"
export PROOFT5_SUFU_FULL_EXECUTOR="${PROOFT5_SUFU_FULL_EXECUTOR:-/data2/x/hzc/.local/sufu-builds/prooft5-origin-verified/executor/run}"
export PROOFT5_SUFU_DEPS="${PROOFT5_SUFU_DEPS:-/data2/x/hzc/.local/sufu-deps}"
export PROOFT5_SUFU_BUILD_DIR="${PROOFT5_SUFU_BUILD_DIR:-/data2/x/hzc/.local/sufu-builds/prooft5-origin-verified}"

export PATH="${PROOFT5_JAVA_HOME}/bin:/home/zchuang/.opam/with-coq-8.20.1/bin:/home/zchuang/.opam/default/bin:${PATH}"
export PKG_CONFIG_PATH="${PROOFT5_SUFU_DEPS}/lib/pkgconfig${PKG_CONFIG_PATH:+:${PKG_CONFIG_PATH}}"
export LD_LIBRARY_PATH="${PROOFT5_SUFU_DEPS}/lib:${PROOFT5_ROOT}/SuFu/SuFu_origin/thirdparty/z3-z3-4.13.0/build:${PROOFT5_ROOT}/SuFu/SuFu_origin/thirdparty/gurobi912/linux64/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"
