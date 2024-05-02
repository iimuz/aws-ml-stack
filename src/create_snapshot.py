"""開発用のEC2インスタンスからスナップショットを作成するスクリプト.

利用例:

```sh
`python src/create_ec2_spot_instance.py --profile AWS_PROFILE
```
"""

import json
import logging
import sys
import time
from argparse import ArgumentParser
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path

import boto3
from pydantic import BaseModel, ConfigDict, Field

from src.awscdk.stack_config import StackConfig
from src.internal.datetime_encoder import DateTimeEncoder

_logger = logging.getLogger(__name__)


class _RunConfig(BaseModel):
    """スクリプト実行のためのオプション."""

    aws_profile: str = Field(description="AWS Profile.")

    volume_id: str = Field(default=None, description="Volume ID.")

    verbosity: int = Field(description="ログレベル.")

    model_config = ConfigDict(frozen=True)


def _main() -> None:
    """スクリプトのエントリポイント."""
    # 実行時引数の読み込み
    config = _parse_args()

    # 作業ディレクトリの設定
    script_filepath = Path(__file__)
    data_dir = Path(__file__).parents[1] / "data"
    processed_dir = data_dir / "processed" / script_filepath.stem
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

    # スナップショットの作成
    _logger.info("Creating snapshot ...")
    session = boto3.Session(profile_name=config.aws_profile)
    ec2 = session.client("ec2")
    description_message = f"{stack_config.stack_name}-ec2-snapshot"
    snapshot = ec2.create_snapshot(
        VolumeId=config.volume_id, Description=description_message
    )

    # スナップショット情報の保存
    datetime_str = time.strftime("%Y%m%d%H%M%S")
    filepath = processed_dir / f"snapshot_{datetime_str}.json"
    with filepath.open("w") as f:
        json.dump(snapshot, f, cls=DateTimeEncoder, indent=2)
    _logger.info("Save snapshot info: %s", filepath)


def _parse_args() -> _RunConfig:
    """スクリプト実行のための引数を読み込む."""
    parser = ArgumentParser(description="EC2インスタンスを生成する.")

    parser.add_argument("volume_id", help="Volume ID.")

    parser.add_argument("-p", "--aws-profile", help="AWS Profile.")

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
