#!/bin/bash

DIR=$(realpath "$(dirname "$0")")
cd "$DIR"

if [[ ! -d mpp ]]; then
  git clone https://github.com/rockchip-linux/mpp.git
fi

set -xeo pipefail

cd mpp
cmake . \
  -DBUILD_SHARED_LIBS=OFF \
  -DBUILD_TEST=OFF \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PWD/usr-local"
make -j5 install

# Cleanup unneeded files to avoid linking to .so files
rm -rf usr-local/lib/librockchip*.so*
