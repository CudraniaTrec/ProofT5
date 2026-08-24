#!/usr/bin/env bash
set -euo pipefail

cd /data2/x/hzc/prooft5/third_party/baselines/eclipse.jdt.ls

JDT_BUILD_JAVA_HOME="${PROOFT5_JDT_BUILD_JAVA_HOME:-${PROOFT5_JAVA_HOME:-/data2/x/hzc/.local/jdks/temurin17}}"
if [ ! -x "$JDT_BUILD_JAVA_HOME/bin/java" ]; then
  printf 'invalid JDK: %s\n' "$JDT_BUILD_JAVA_HOME" >&2
  exit 66
fi
export JAVA_HOME="$JDT_BUILD_JAVA_HOME"
export PATH="$JDT_BUILD_JAVA_HOME/bin:$PATH"
./mvnw clean verify -DskipTests=true

launcher=(org.eclipse.jdt.ls.product/target/repository/plugins/org.eclipse.equinox.launcher_*.jar)
if [ "${#launcher[@]}" -eq 0 ] || [ ! -f "${launcher[0]}" ]; then
  printf 'JDT LS build finished without a launcher jar\n' >&2
  exit 70
fi
printf 'Modified JDT LS launcher: %s\n' "${launcher[0]}"
