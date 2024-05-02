"""開発用のEC2インスタンスを作成するときのスクリプト.

利用例:

```sh
`python src/ec2_request.py --profile AWS_PROFILE
```
"""

import json
import logging
import sys
from argparse import ArgumentParser
from enum import Enum
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

import boto3
from pydantic import BaseModel, ConfigDict, Field

from src.awscdk.stack_config import StackConfig
from src.internal.datetime_encoder import DateTimeEncoder
from src.internal.ec2_spot_instance import SpotInstance
from src.internal.stack_output import StackOutput

_logger = logging.getLogger(__name__)


class _InstanceType(Enum):
    """EC2インスタンスのタイプ.

    ここに記載しているインスタンスタイプは、利用することが多いものを記載している。
    """

    # Free tier
    T2_MICRO = "t2.micro"
    # 4 vCPU, 16GB RAM
    M5_XLARGE = "m5.xlarge"
    # 4 vCPU, 16GB RAM, GPU 1(Tesla T4, 16GB VRAM)
    G4DN_XLARGE = "g4dn.xlarge"


class _RunConfig(BaseModel):
    """スクリプト実行のためのオプション."""

    aws_profile: str = Field(description="AWS Profile.")

    ssh_key_name: str = Field(default="ml-dev-key", description="SSH Key Name.")
    instance_type: _InstanceType = Field(
        default=_InstanceType.T2_MICRO, description="Instance Type."
    )

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

    # CDKから情報を取得
    stack_config = StackConfig.create_dev()
    stack_output = StackOutput.load_from_stack(
        config=stack_config, profile=config.aws_profile
    )

    # インスタンスの生成
    _logger.info("Launching EC2 ...")
    session = boto3.Session(profile_name=config.aws_profile)
    spot_instance = SpotInstance(session=session, log_dir=processed_dir)
    spot_instance.request(
        tag_name=stack_config.tag_name,
        security_group_id=stack_output.security_group_id,
        ssh_key_name=config.ssh_key_name,
        instance_type=config.instance_type.value,
    )
    spot_instance.wait_until_instance_running()
    _logger.info(json.dumps(spot_instance.describe(), cls=DateTimeEncoder, indent=2))


def _parse_args() -> _RunConfig:
    """スクリプト実行のための引数を読み込む."""
    parser = ArgumentParser(description="EC2インスタンスを生成する.")

    parser.add_argument("-p", "--aws-profile", help="AWS Profile.")

    parser.add_argument("-k", "--ssh-key-name", help="ssh key name for accessing EC2.")
    parser.add_argument(
        "-t",
        "--instance-type",
        default=_InstanceType.T2_MICRO,
        choices=[v.value for v in _InstanceType],
        help="Instance Type.",
    )

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
