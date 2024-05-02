"""AWS EC2のスポットインスタンスを管理するためのモジュール."""

import json
import os
import time
from pathlib import Path

from boto3 import Session
from mypy_boto3_ec2.literals import InstanceTypeType
from mypy_boto3_ec2.type_defs import (
    BlockDeviceMappingTypeDef,
    InstanceMarketOptionsRequestTypeDef,
    InstanceMetadataOptionsRequestTypeDef,
    InstanceNetworkInterfaceSpecificationTypeDef,
    InstanceTypeDef,
    PrivateDnsNameOptionsRequestTypeDef,
    TagSpecificationTypeDef,
)

from src.internal.datetime_encoder import DateTimeEncoder


class SpotInstance:
    """AWS EC2のスポットインスタンスを管理するクラス."""

    instance_id: str | None = None
    spot_instance_request_id: str | None = None

    def __init__(self: "SpotInstance", session: Session, log_dir: Path) -> None:
        """初期化メソッド."""
        self._ec2 = session.client("ec2")
        self._log_dir = log_dir / "spot_instance"

        self._log_dir.mkdir(exist_ok=True)

    def request(
        self: "SpotInstance",
        tag_name: str,
        security_group_id: str,
        ssh_key_name: str,
        instance_type: InstanceTypeType = "t2.micro",
    ) -> None:
        """スポットインスタンスのリクエストを行う."""
        ami = _get_ami()
        tag_specifications = _get_tag_specifications(tag_name)
        instance_market_options = _get_instance_market_options()
        block_device = _get_block_device_mapping()
        network_interface = _get_network_interface([security_group_id])
        metadata_options = _get_instance_metadata_options()
        private_dns_name_options = _get_private_dns_name_options()
        response = self._ec2.run_instances(
            ImageId=ami,
            MaxCount=1,
            MinCount=1,
            InstanceType=instance_type,
            TagSpecifications=[tag_specifications],
            KeyName=ssh_key_name,
            InstanceMarketOptions=instance_market_options,
            BlockDeviceMappings=[block_device],
            NetworkInterfaces=[network_interface],
            MetadataOptions=metadata_options,
            PrivateDnsNameOptions=private_dns_name_options,
        )

        instance = response["Instances"][0]
        instance_id = instance.get("InstanceId", "")
        spot_instance_request_id = instance.get("SpotInstanceRequestId", "")
        state = instance.get("State", {})
        unix_epoch = int(time.time())
        _save_log(
            log_dir=self._log_dir,
            unix_epoch=unix_epoch,
            instance_id=instance_id,
            spot_instance_request_id=spot_instance_request_id,
            status=(state.get("Code", -1), state.get("Name", "")),
        )

        self.instance_id = instance_id
        self.spot_instance_request_id = spot_instance_request_id

    def wait_until_instance_running(self: "SpotInstance") -> None:
        """インスタンスが起動するまで待機する."""
        if self.instance_id is None:
            message = "Instance ID is not set."
            raise ValueError(message)

        waiter = self._ec2.get_waiter("instance_running")
        waiter.wait(InstanceIds=[self.instance_id])

    def describe(self: "SpotInstance") -> InstanceTypeDef:
        """インスタンスのリクエスト情報を取得する."""
        if self.instance_id is None:
            message = "Instance ID is not set."
            raise ValueError(message)

        response = self._ec2.describe_instances(
            InstanceIds=[self.instance_id],
        )

        return response["Reservations"][0].get("Instances", [{}])[0]

    def terminate(self: "SpotInstance") -> None:
        """インスタンスを削除する."""
        if self.instance_id is None:
            message = "Instance ID is not set."
            raise ValueError(message)
        if self.spot_instance_request_id is None:
            message = "Spot Instance Request ID is not set."
            raise ValueError(message)

        # Spot Requestをキャンセル
        response = self._ec2.cancel_spot_instance_requests(
            SpotInstanceRequestIds=[self.spot_instance_request_id]
        )
        spot_cancel_request = response.get("CancelledSpotInstanceRequests", [{}])[0]
        instance_id = spot_cancel_request.get("InstanceId", "")
        spot_instance_request_id = spot_cancel_request.get("SpotInstanceRequestId", "")
        state = spot_cancel_request.get("State", "")
        _save_log(
            log_dir=self._log_dir,
            unix_epoch=int(time.time()),
            instance_id=self.instance_id,
            spot_instance_request_id=spot_instance_request_id,
            status=(-1, state),
        )

        # インスタンスを削除
        response = self._ec2.terminate_instances(InstanceIds=[self.instance_id])
        instance_terminate_request = response.get("TerminatingInstances", [{}])[0]
        instance_id = instance_terminate_request.get("InstanceId", "")
        state = instance_terminate_request.get("CurrentState", {})
        _save_log(
            log_dir=self._log_dir,
            unix_epoch=int(time.time()),
            instance_id=instance_id,
            spot_instance_request_id=spot_instance_request_id,
            status=(state.get("Code", -1), state.get("Name", "")),
        )

        self.instance_id = None
        self.spot_instance_request_id = None

    def load_latest(self: "SpotInstance") -> None:
        """最新のインスタンス情報を取得する."""
        log_filepath = _search_latest_instance_log(self._log_dir)
        if log_filepath is None:
            message = "Log file is not found."
            raise FileNotFoundError(message)
        logs = _load_log(log_filepath)
        if len(logs) == 0:
            message = "Log data is not found: {log_filepath}"
            raise ValueError(message)
        log = logs[-1]  # 最後が最新のログ

        instance_id = log.get("instance_id", None)
        if instance_id is None:
            message = f"Instance ID is not found. file: {log_filepath}"
            raise ValueError(message)
        spot_request_id = log.get("spot_instance_request_id", None)
        if spot_request_id is None:
            message = f"Spot Instance Request ID is not found. file: {log_filepath}"
            raise ValueError(message)

        self.instance_id = instance_id
        self.spot_instance_request_id = spot_request_id

    @property
    def availability_zone(self: "SpotInstance") -> str:
        """インスタンスのアベイラビリティゾーンを取得する."""
        if self.instance_id is None:
            message = "Instance ID is not set."
            raise ValueError(message)

        meta = self.describe()
        return meta.get("Placement", {}).get("AvailabilityZone", "")


def _get_ami() -> str:
    """AMIのIDを取得する."""
    # Deep Learning Base Ubuntu20.04(cuda driver and docker installed)
    return "ami-08b9a877bc0de2016"


def _get_tag_specifications(tag_name: str) -> TagSpecificationTypeDef:
    """タグ仕様を取得する."""
    return {
        "ResourceType": "instance",
        "Tags": [{"Key": "Name", "Value": tag_name}],
    }


def _get_block_device_mapping() -> BlockDeviceMappingTypeDef:
    """ルートのブロックデバイスマッピングを取得する."""
    return {
        "DeviceName": "/dev/sda1",
        "Ebs": {
            "SnapshotId": "snap-0eb5dd914ea8dae65",  # DL ami ubuntu20.04
            "DeleteOnTermination": True,
            "VolumeType": "gp3",
            "VolumeSize": 128,
            "Iops": 3000,
            "Throughput": 125,
        },
    }


def _get_instance_market_options() -> InstanceMarketOptionsRequestTypeDef:
    """インスタンスのマーケットオプションを取得する."""
    return {
        "MarketType": "spot",
        "SpotOptions": {"SpotInstanceType": "one-time"},
    }


def _get_network_interface(
    security_group_ids: list[str],
) -> InstanceNetworkInterfaceSpecificationTypeDef:
    """ネットワークインターフェースを取得する."""
    return {
        "AssociatePublicIpAddress": True,
        "DeviceIndex": 0,
        "Groups": security_group_ids,
    }


def _get_instance_metadata_options() -> InstanceMetadataOptionsRequestTypeDef:
    """インスタンスのメタデータオプションを取得する."""
    return {
        "HttpTokens": "required",
        "HttpEndpoint": "enabled",
        "HttpPutResponseHopLimit": 2,
    }


def _get_private_dns_name_options() -> PrivateDnsNameOptionsRequestTypeDef:
    """プライベートDNS名のオプションを取得する."""
    return {
        "HostnameType": "ip-name",
        "EnableResourceNameDnsARecord": True,
        "EnableResourceNameDnsAAAARecord": False,
    }


def _load_log(filepath: Path) -> list[dict]:
    """ログを読み込む."""
    with filepath.open("r") as f:
        return [json.loads(line) for line in f]


def _save_log(
    log_dir: Path,
    unix_epoch: int,
    instance_id: str,
    spot_instance_request_id: str,
    status: tuple[int, str],  # (status_code, status_name)
) -> None:
    """ログを保存する."""
    filepath = _search_instance_log(log_dir, instance_id)
    if filepath is None:
        filepath = log_dir / f"{unix_epoch}_{instance_id}.json"

    with filepath.open("a") as f:
        json.dump(
            {
                "datetime": unix_epoch,
                "instance_id": instance_id,
                "spot_instance_request_id": spot_instance_request_id,
                "status": {
                    "code": status[0],
                    "name": status[1],
                },
            },
            f,
            cls=DateTimeEncoder,
        )
        f.write(os.linesep)


def _search_instance_log(log_dir: Path, instance_id: str) -> Path | None:
    """インスタンスのログファイルパスを返す."""
    files = sorted(log_dir.glob(f"*_{instance_id}.json"))
    if len(files) == 0:
        return None

    return files[-1]


def _search_latest_instance_log(log_dir: Path) -> Path | None:
    """最新のインスタンスのログファイルパスを返す."""
    files = sorted(log_dir.glob("*.json"))
    if len(files) == 0:
        return None

    return files[-1]
