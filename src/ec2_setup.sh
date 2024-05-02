#!/usr/bin/env bash
#
# EC2をセットアップするスクリプト

# セカンドディスクを有効化
lsblk
sudo mkfs -t ext4 /dev/xvdb
sudo mkdir /data
sudo mount /dev/xvdb /data
echo '/dev/xvdb /data ext4 defaults,nofail 0 0' | sudo tee -a /etc/fstab
sudo chown -R ubuntu:ubuntu /data
sudo chmod -R 764 /data

# homebrewのインストール
# See: <https://brew.sh/ja/>
# CI=1: <https://github.com/Homebrew/install/issues/369#issuecomment-824250909>
CI=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> $HOME/.bashrc
source $HOME/.bashrc

# 環境の構築
pushd /data
  mkdir -p src/github.com/iimuz && pushd $_
    git clone https://github.com/iimuz/dotfiles.git
    pushd dotfiles
      bash setup.sh
      source $HOME/.bashrc
      brew bundle install
    popd
  popd
popd
ln -s /data/src


# zshの設定
# chshでデフォルトシェルを変えられなかったのでpasswdを編集
sudo sh -c "echo $(which zsh) >> /etc/shells"
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> $HOME/.zshrc
sudo chsh -s $(which zsh)
sudo sed -i 's|ubuntu:/bin/bash|ubuntu:ubuntu:/home/linuxbrew/.linuxbrew/bin/bin/zsh|g' /etc/passwd

# 言語の設定
asdf plugin add nodejs
asdf install nodejs 20.12.2
asdf global nodejs 20.12.2

asdf plugin add python
asdf install python 3.11.9
asdf global python 3.11.9
