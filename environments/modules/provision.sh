#!/usr/bin/env bash
# Run inside the dedicated Ubuntu ARM64 VM, never on the macOS host.
set -euo pipefail
ROOT_DIR="${CHIPBENCH_MODULE_ROOT:-$HOME/chipbench-modules}"
PICO_REV=ef203c2b0a3fb793280f5114941416c425c5b461
ORFS_REV=c5310d7ffdd5f8a1eed83089697631548cc08a99
OPENROAD_REV=f131605002c80444f79b18e95e0c7cb657ec024d
mkdir -p "$ROOT_DIR/fixtures" "$ROOT_DIR/results"
sudo -E apt-get update
sudo -E apt-get install -y git make python3 build-essential iverilog verilator yosys z3 gcc-riscv64-unknown-elf klayout
checkout() {
  local url="$1" dest="$2" rev="$3"
  if [ ! -d "$dest/.git" ]; then git clone --no-checkout "$url" "$dest"; fi
  git -C "$dest" fetch origin "$rev"
  git -C "$dest" checkout --detach "$rev"
}
checkout https://github.com/YosysHQ/picorv32.git "$ROOT_DIR/picorv32" "$PICO_REV"
checkout https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts.git "$ROOT_DIR/orfs" "$ORFS_REV"
git -C "$ROOT_DIR/orfs" submodule update --init tools/OpenROAD
test "$(git -C "$ROOT_DIR/orfs/tools/OpenROAD" rev-parse HEAD)" = "$OPENROAD_REV"
git -C "$ROOT_DIR/orfs/tools/OpenROAD" submodule update --init
cd "$ROOT_DIR/orfs/tools/OpenROAD"
sudo -E bash etc/DependencyInstaller.sh -all
bash etc/Build.sh -no-gui -threads=4 -prefix="$ROOT_DIR/tools"
