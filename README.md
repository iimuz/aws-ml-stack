# AWSを利用したMachine Learning環境構築

## 概要

AWSを利用してMachine Learningを行うためのリソースを作成します。

## 環境構築方法

初回で環境を構築する場合は、下記のコマンドで環境構築を行います。

```sh
task setup
```

パッケージの更新を行う場合は下記のようにします。

```sh
task update-requirements
```

## Tips

### よく使う起動コマンド

作業をする環境は下記で作成する。
`TAILSCALE_AUTH_KEY` は、tailscaleで `Reusable` をfalseのままで発行して設定する。

```sh
# EC2の起動
task ec2-request AWS_PROFILE=profile INSTANCE_TYPE=m5.large TAILSCALE_AUTH_KEY=... -- -vv
scp src/setup_ec2_* ubuntu@aws-ec2-ml-dev:~/

# EC2に接続して実行環境の設定
ssh ubuntu@aws-ec2-ml-dev
bash setup_ec2_1stage.sh
source .bashrc
bash setup_ec2_2stage.sh
sudo reboot
```

VSCode webが必要な場合は下記を実施して、起動する。

```sh
scp src/code_web_* ubuntu@aws-ec2-ml-dev:~/

ssh ubuntu@aws-ec2-ml-dev
bash code_web_install.sh
bash code_web_run.sh
```
