"""EC2にアタッチするVolumeを作成するスクリプト."""

import json
import logging
import sys
from argparse import ArgumentParser
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

import boto3
from pydantic import BaseModel, ConfigDict, Field

from src.internal.datetime_encoder import DateTimeEncoder
from src.internal.ec2_spot_instance import SpotInstance
from src.internal.ec2_volume import EC2Volume

_logger = logging.getLogger(__name__)


class _RunConfig(BaseModel):
    """スクリプト実行のためのオプション."""

    aws_profile: str = Field(description="AWS Profile.")

    volume_size: int = Field(ge=10, description="Volume Size.")
    device: str = Field(description="Device Name.")

    verbosity: int = Field(description="ログレベル.")

    model_config = ConfigDict(frozen=True)


def _main() -> None:
    """スクリプトのエントリポイント."""
    # 実行時引数の読み込み
    config = _parse_args()

    # 作業ディレクトリの設定
    script_filepath = Path(__file__)
    data_dir = Path(__file__).parents[1] / "data"
    processed_dir = data_dir / "processed"
    processed_dir.mkdir(exist_ok=True)

    # ログ設定
    loglevel = {
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG,
    }.get(config.verbosity, logging.DEBUG)
    log_filepath = Path("data/interim") / f"{script_filepath.stem}.log"
    log_filepath.parent.mkdir(exist_ok=True)
    _setup_logger(log_filepath, loglevel=loglevel)
    _logger.info(config)

    # EBS Volumeを作成もしくは既存のVolumeをEC2インスタンスにアタッチする
    cdk_context = json.loads(Path("cdk.context.json").read_text())
    aws_region = cdk_context.get("aws:cdk:region", None)
    if aws_region is None:
        message = "cannot get AWS Region from CDK context."
        raise ValueError(message)
    session = boto3.Session(profile_name=config.aws_profile, region_name=aws_region)

    spot_instance = SpotInstance(session=session, log_dir=processed_dir)
    spot_instance.load_latest()
    availability_zone = spot_instance.availability_zone

    volume = EC2Volume(session=session, log_dir=processed_dir)
    volume.load_latest()
    if volume.volume_id is None or volume.state != "available":
        volume.create(
            volume_size=config.volume_size, availability_zone=availability_zone
        )
        volume.wait_until_available()
    _logger.info(json.dumps(volume.describe(), cls=DateTimeEncoder, indent=2))

    volume.attach(instance_id=spot_instance.instance_id, device=config.device)


def _parse_args() -> _RunConfig:
    """スクリプト実行のための引数を読み込む."""
    parser = ArgumentParser(description="EC2インスタンスを生成する.")

    parser.add_argument("-p", "--aws-profile", help="AWS Profile.")

    parser.add_argument("-s", "--volume-size", default=128, help="Volume size.")
    parser.add_argument("-d", "--device", default="/dev/sdf", help="Volume size.")

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
