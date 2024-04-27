"""AWS CDKで作成するスタック."""

from typing import Self

import aws_cdk as cdk
import requests
from aws_cdk import (
    aws_ec2 as ec2,
)
from constructs import Construct


class MyProjectStack(cdk.Stack):
    """AWS CDKで作成するスタック.

    CDKのスタックを作成するためのクラス
    このクラスでは、EC2インスタンスで利用するセキュリティグループを作成する。
    このセキュリティグループは、SSH接続を許可する。
    """

    def __init__(self: Self, scope: Construct, stack_id: str, **kwargs) -> None:
        """スタックを作成する."""
        super().__init__(scope, stack_id, **kwargs)

        # Default VPCを取得する
        vpc = ec2.Vpc.from_lookup(
            self,
            "MyVpc",
            is_default=True,
        )

        # セキュリティグループを作成する
        # このセキュリティグループは、SSH接続を許可する
        # また、このセキュリティグループは、インターネットからのアクセスを許可しない
        # このセキュリティグループは、EC2インスタンスにアタッチされる
        # 接続元のIPは指定したIPのみ許可する(IP: 128.0.0.1)
        sg = ec2.SecurityGroup(
            self,
            "MySecurityGroup",
            vpc=vpc,
            description="Allow SSH access from the world",
            allow_all_outbound=True,
        )

        ip_address = _get_amazon_global_ip()
        sg.add_ingress_rule(
            ec2.Peer.ipv4(ip_address), ec2.Port.tcp(22), "Allow SSH access."
        )


def _get_amazon_global_ip() -> str:
    """グローバルIPアドレスを取得する."""
    # AmazonのIP確認アドレスにリクエストを送信して公開IPアドレスを取得
    response = requests.get("https://checkip.amazonaws.com")
    response.raise_for_status()

    return f"{response.text.strip()}/32"
