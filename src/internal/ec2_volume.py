"""AWS EC2 Volumeを管理するためのモジュール."""

import json
import os
import time
from pathlib import Path

from boto3 import Session
from botocore.exceptions import ClientError
from mypy_boto3_ec2.type_defs import VolumeTypeDef


class EC2Volume:
    """AWS EC2のVolumeを管理するクラス."""

    volume_id: str | None = None

    def __init__(self: "EC2Volume", session: Session, log_dir: Path) -> None:
        """初期化メソッド."""
        self._ec2 = session.client("ec2")
        self._log_dir = log_dir / "ec2_volume"

        self._log_dir.mkdir(exist_ok=True)

    def create(
        self: "EC2Volume",
        volume_size: int,
        availability_zone: str,
    ) -> None:
        """Volumeを作成する."""
        volume = self._ec2.create_volume(
            AvailabilityZone=availability_zone,
            Size=volume_size,  # GB
            VolumeType="gp3",
        )
        self.volume_id = volume["VolumeId"]

        _save_log(
            log_dir=self._log_dir,
            unix_epoch=int(time.time()),
            volume_id=self.volume_id,
            state=volume["State"],
        )

    def attach(self: "EC2Volume", instance_id: str, device: str) -> None:
        """Volumeをインスタンスにアタッチする."""
        if self.volume_id is None:
            message = "Volume ID is not found."
            raise ValueError(message)

        self._ec2.attach_volume(
            Device=device,
            InstanceId=instance_id,
            VolumeId=self.volume_id,
        )

        _save_log(
            log_dir=self._log_dir,
            unix_epoch=int(time.time()),
            volume_id=self.volume_id,
            state="attach",
        )

    def delete(self: "EC2Volume") -> None:
        """Volumeを削除する."""
        if self.volume_id is None:
            message = "Volume ID is not found."
            raise ValueError(message)

        self._ec2.delete_volume(VolumeId=self.volume_id)

        _save_log(
            log_dir=self._log_dir,
            unix_epoch=int(time.time()),
            volume_id=self.volume_id,
            state="delete",
        )

    def describe(self: "EC2Volume") -> VolumeTypeDef:
        """Volumeの情報を取得する."""
        if self.volume_id is None:
            message = "Volume ID is not found."
            raise ValueError(message)

        response = self._ec2.describe_volumes(VolumeIds=[self.volume_id])

        return response["Volumes"][0]

    def wait_until_available(self: "EC2Volume") -> None:
        """Volumeが利用可能になるまで待機する."""
        if self.volume_id is None:
            message = "Volume ID is not found."
            raise ValueError(message)

        waiter = self._ec2.get_waiter("volume_available")
        waiter.wait(VolumeIds=[self.volume_id])

    def load_latest(self: "EC2Volume") -> None:
        """最新のインスタンス情報を取得する."""
        log_filepath = _search_latest_volume_log(self._log_dir)
        if log_filepath is None:
            message = "Log file is not found."
            raise FileNotFoundError(message)
        logs = _load_log(log_filepath)
        if len(logs) == 0:
            message = "Log data is not found: {log_filepath}"
            raise ValueError(message)
        log = logs[-1]  # 最後が最新のログ

        volume_id = log.get("volume_id", None)
        if volume_id is None:
            message = f"Volume ID is not found. file: {log_filepath}"
            raise ValueError(message)

        self.volume_id = volume_id

    @property
    def state(self: "EC2Volume") -> str:
        """Volumeの状態を返す."""
        if self.volume_id is None:
            message = "Volume ID is not found."
            raise ValueError(message)

        try:
            response = self._ec2.describe_volumes(VolumeIds=[self.volume_id])
        except ClientError:
            return "not-found"

        volume = response["Volumes"][0]
        return volume.get("State", "")


def _load_log(filepath: Path) -> list[dict]:
    """ログを読み込む."""
    with filepath.open("r") as f:
        return [json.loads(line) for line in f]


def _save_log(
    log_dir: Path,
    unix_epoch: int,
    volume_id: str,
    state: str,  # (status_code, status_name)
) -> None:
    """ログを保存する."""
    filepath = _search_instance_log(log_dir, volume_id)
    if filepath is None:
        filepath = log_dir / f"{unix_epoch}_{volume_id}.json"

    with filepath.open("a") as f:
        json.dump(
            {
                "datetime": unix_epoch,
                "volume_id": volume_id,
                "state": state,
            },
            f,
        )
        f.write(os.linesep)


def _search_instance_log(log_dir: Path, volume_id: str) -> Path | None:
    """インスタンスのログファイルパスを返す."""
    files = sorted(log_dir.glob(f"*_{volume_id}.json"))
    if len(files) == 0:
        return None

    return files[-1]


def _search_latest_volume_log(log_dir: Path) -> Path | None:
    """最新のインスタンスのログファイルパスを返す."""
    files = sorted(log_dir.glob("*.json"))
    if len(files) == 0:
        return None

    return files[-1]
