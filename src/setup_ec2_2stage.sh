#!/usr/bin/env bash
#
# EC2をセットアップするスクリプト
set -eu
set -o pipefail

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

# 環境をzshに再設定
echo "source /etc/profile.d/dlami.sh" >> $HOME/.zshrc  # DL AMIを利用する場合にnvccなどにパスを通す

pushd /data/src/github.com/iimuz/dotfiles
  SHELL="$(which zsh)" bash setup.sh
popd
