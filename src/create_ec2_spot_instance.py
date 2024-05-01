"""開発用のEC2インスタンスを作成するときのスクリプト.

利用例:

```sh
`python src/create_ec2_spot_instance.py --profile AWS_PROFILE
```
"""

import logging
import sys
import time
from argparse import ArgumentParser
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

import boto3
from pydantic import BaseModel, ConfigDict, Field

from src.awscdk.stack_config import StackConfig
from src.internal.stack_output import StackOutput

if TYPE_CHECKING:
    from mypy_boto3_ec2.type_defs import (
        BlockDeviceMappingTypeDef,
        InstanceMarketOptionsRequestTypeDef,
        InstanceMetadataOptionsRequestTypeDef,
        InstanceNetworkInterfaceSpecificationTypeDef,
        PrivateDnsNameOptionsRequestTypeDef,
        TagSpecificationTypeDef,
    )

_logger = logging.getLogger(__name__)


class _RunConfig(BaseModel):
    """スクリプト実行のためのオプション."""

    aws_profile: str = Field(description="AWS Profile.")

    ssh_key_name: str = Field(default="ml-dev-key", description="SSH Key Name.")

    verbosity: int = Field(description="ログレベル.")

    model_config = ConfigDict(frozen=True)


def _main() -> None:
    """スクリプトのエントリポイント."""
    # 実行時引数の読み込み
    config = _parse_args()

    # ログ設定
    loglevel = {
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG,
    }.get(config.verbosity, logging.DEBUG)
    script_filepath = Path(__file__)
    log_filepath = Path("data/interim") / f"{script_filepath.stem}.log"
    log_filepath.parent.mkdir(exist_ok=True)
    _setup_logger(log_filepath, loglevel=loglevel)
    _logger.info(config)

    stack_config = StackConfig.create_dev()
    stack_output = StackOutput.load_from_stack(
        config=stack_config, profile=config.aws_profile
    )
    _logger.info(stack_output.security_group_id)

    ami: str = (
        # Deep Learning Base Ubuntu20.04(cuda driver and docker installed)
        "ami-08b9a877bc0de2016"
    )
    instance_type: str = "t2.micro"  # free

    tag_specifications: TagSpecificationTypeDef = {
        "ResourceType": "instance",
        "Tags": [{"Key": "Name", "Value": stack_config.tag_name}],
    }
    block_device: BlockDeviceMappingTypeDef = {
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "SnapshotId": "snap-0ae02beb4873352c7",  # cpu ubuntu
            "DeleteOnTermination": True,
            "VolumeType": "gp3",
            "VolumeSize": 30,
            "Iops": 3000,
            "Throughput": 125,
        },
    }
    instance_market_options: InstanceMarketOptionsRequestTypeDef = {
        "MarketType": "spot",
        "SpotOptions": {"SpotInstanceType": "one-time"},
    }
    network_interface: InstanceNetworkInterfaceSpecificationTypeDef = {
        "AssociatePublicIpAddress": True,
        "DeviceIndex": 0,
        "Groups": [stack_output.security_group_id],
    }
    metadata_options: InstanceMetadataOptionsRequestTypeDef = {
        "HttpTokens": "required",
        "HttpEndpoint": "enabled",
        "HttpPutResponseHopLimit": 2,
    }
    private_dns_name_options: PrivateDnsNameOptionsRequestTypeDef = {
        "HostnameType": "ip-name",
        "EnableResourceNameDnsARecord": True,
        "EnableResourceNameDnsAAAARecord": False,
    }

    # 設定値のログ出力
    _logger.info("tag specifications: %s", tag_specifications)
    _logger.info("block device: %s", block_device)
    _logger.info("instance market options: %s", instance_market_options)
    _logger.info("network interface: %s", network_interface)
    _logger.info("metadata options: %s", metadata_options)
    _logger.info("private dns name options: %s", private_dns_name_options)

    # インスタンスの生成
    _logger.info("Launching EC2 ...")
    session = boto3.Session(profile_name=config.aws_profile)
    ec2 = session.client("ec2")
    instances = ec2.run_instances(
        ImageId=ami,
        MaxCount=1,
        MinCount=1,
        InstanceType=instance_type,
        TagSpecifications=[tag_specifications],
        KeyName=config.ssh_key_name,
        InstanceMarketOptions=instance_market_options,
        BlockDeviceMappings=[block_device],
        NetworkInterfaces=[network_interface],
        MetadataOptions=metadata_options,
        PrivateDnsNameOptions=private_dns_name_options,
    )
    time.sleep(5.0)
    instance = instances["Instances"][0]
    _logger.info(instance)


def _parse_args() -> _RunConfig:
    """スクリプト実行のための引数を読み込む."""
    parser = ArgumentParser(description="EC2インスタンスを生成する.")

    parser.add_argument("-p", "--aws-profile", help="AWS Profile.")

    parser.add_argument("-k", "--ssh-key-name", help="ssh key name for accessing EC2.")

    parser.add_argument(
        "-v",
        "--verbosity",
        action="count",
        default=0,
        help="詳細メッセージのレベルを設定.",
    )

    args = parser.parse_args()

    return _RunConfig(**vars(args))


def _setup_logger(filepath: Path | None, loglevel: int) -> None:
    """ロガー設定を行う.

    Parameters
    ----------
    filepath : Path | None
        ログ出力するファイルパス. Noneの場合はファイル出力しない.

    loglevel : int
        出力するログレベル.

    Notes
    -----
    ファイル出力とコンソール出力を行うように設定する。

    """
    _logger.setLevel(loglevel)

    # consoleログ
    console_handler = StreamHandler()
    console_handler.setLevel(loglevel)
    console_handler.setFormatter(
        Formatter("[%(levelname)7s] %(asctime)s (%(name)s) %(message)s")
    )
    _logger.addHandler(console_handler)

    # ファイル出力するログ
    # 基本的に大量に利用することを想定していないので、ログファイルは多くは残さない。
    if filepath is not None:
        file_handler = RotatingFileHandler(
            filepath,
            encoding="utf-8",
            mode="a",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=1,
        )
        file_handler.setLevel(loglevel)
        file_handler.setFormatter(
            Formatter("[%(levelname)7s] %(asctime)s (%(name)s) %(message)s")
        )
        _logger.addHandler(file_handler)


if __name__ == "__main__":
    try:
        _main()
    except Exception:
        _logger.exception("Unhandled error")
        sys.exit(1)
