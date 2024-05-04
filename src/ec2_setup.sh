#!/usr/bin/env bash
#
# EC2をセットアップするスクリプト
set -eu
set -o pipefail

# セカンドディスクを有効化
readonly DEVICE_NAME="nvme1n1"
readonly MOUNT_POINT="/data"
lsblk
sudo mkfs -t ext4 /dev/$DEVICE_NAME
sudo mkdir $MOUNT_POINT
sudo mount /dev/$DEVICE_NAME $MOUNT_POINT
echo "/dev/$DEVICE_NAME $MOUNT_POINT ext4 defaults,nofail 0 0" | sudo tee -a /etc/fstab
sudo chown -R ubuntu:ubuntu $MOUNT_POINT
sudo chmod -R 764 $MOUNT_POINT

# homebrewのインストール
# See: <https://brew.sh/ja/>
# CI=1: <https://github.com/Homebrew/install/issues/369#issuecomment-824250909>
CI=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> $HOME/.bashrc
set +eu && source $HOME/.bashrc && set -eu

# 環境の構築
pushd /data
  mkdir -p src/github.com/iimuz && pushd $_
    git clone https://github.com/iimuz/dotfiles.git
    pushd dotfiles
      bash setup.sh
      set +eu && source $HOME/.bashrc && set -eu
      brew bundle install
    popd
  popd
popd
ln -s /data/src


# zshの設定
sudo sh -c "echo $(which zsh) >> /etc/shells"
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> $HOME/.zshrc
# sudo chsh -s $(which zsh)
# chshでデフォルトシェルを変えられなかった場合にpasswdを編集
sudo sed -i 's|ubuntu:/bin/bash|ubuntu:/home/linuxbrew/.linuxbrew/bin/zsh|g' /etc/passwd

# 言語の設定
readonly NODEJS_VERSION=20.12.2
asdf plugin add nodejs
asdf install nodejs $NODEJS_VERSION
asdf global nodejs $NODEJS_VERSION

readonly PYTHON_VERSION=3.11.9
asdf plugin add python
asdf install python $PYTHON_VERSION
asdf global python $PYTHON_VERSION

readonly JAVA_VERSION="openjdk.20.0.1"
asdf plugin add java
asdf install java $JAVA_VERSION
asdf global java $JAVA_VERSION
