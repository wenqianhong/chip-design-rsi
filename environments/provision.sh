#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
if [ -n "${CHIPBENCH_BUILD_PROXY:-}" ]; then
  export http_proxy="$CHIPBENCH_BUILD_PROXY" https_proxy="$CHIPBENCH_BUILD_PROXY"
fi
sudo env DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential cmake ninja-build git curl zip unzip tar pkg-config python3 python3-venv libssl-dev iptables
sudo useradd --create-home --shell /bin/bash chipworker 2>/dev/null || true
sudo mkdir -p /opt/chipbench
sudo chown "$(id -u):$(id -g)" /opt/chipbench
cd /opt/chipbench
if [ ! -d ChampSim/.git ]; then git -c http.version=HTTP/1.1 clone --depth 1 https://github.com/ChampSim/ChampSim.git; fi
sudo chown -R "$(id -u):$(id -g)" ChampSim
cd ChampSim
git fetch --depth 1 origin 410cee62d9c429c043ea611325ce00e6c303be2a
git checkout 410cee62d9c429c043ea611325ce00e6c303be2a
git submodule update --init --depth 1
export VCPKG_FORCE_SYSTEM_BINARIES=1
./vcpkg/bootstrap-vcpkg.sh -disableMetrics
./vcpkg/vcpkg install --triplet arm64-linux --disable-metrics
python3 - <<'PY'
import json
from pathlib import Path
configs=[{'executable_name':'baseline','L2C':{'prefetcher':'ip_stride'}},{'executable_name':'no_prefetch','L2C':{'prefetcher':'no'}}]
Path('chipbench-config.json').write_text(json.dumps(configs))
PY
./config.sh chipbench-config.json
make -j2
sudo chown -R root:root /opt/chipbench/ChampSim
sudo chmod -R a+rX /opt/chipbench/ChampSim
sudo mkdir -p /opt/chipbench/traces
sudo sh -c 'dpkg-query -W > /opt/chipbench/packages.txt'
echo 'CHIPBENCH_PROVISION_OK'
