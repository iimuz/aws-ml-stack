#!/usr/bin/env bash
set -eu
set -o pipefail

readonly TEMP_DIR=~/temp-code

mkdir -p $TEMP_DIR
pushd $_

curl -Lk 'https://code.visualstudio.com/sha/download?build=stable&os=cli-alpine-x64' --output vscode_cli.tar.gz
tar -xf vscode_cli.tar.gz
sudo mv code /usr/local/bin/

popd
rm -rf $TEMP_DIR
