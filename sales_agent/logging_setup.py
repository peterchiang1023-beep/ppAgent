"""日誌設定：所有 Agent 動作都寫入 logs/ 資料夾。

- logs/agent_YYYYMMDD.log：人類可讀的文字日誌
- logs/actions_YYYYMMDD.jsonl：結構化動作紀錄（每行一筆 JSON，方便稽核與分析）
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOGGER_NAME = "sales_agent"
_logs_dir: Path | None = None


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """初始化檔案日誌（重複呼叫是安全的）。"""
    global _logs_dir
    _logs_dir = logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    logfile = logs_dir / f"agent_{datetime.now():%Y%m%d}.log"
    if not any(
        isinstance(h, logging.FileHandler) and Path(h.baseFilename) == logfile
        for h in logger.handlers
    ):
        handler = logging.FileHandler(logfile, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def _truncate(value: Any, limit: int = 2000) -> Any:
    """避免日誌過大：長字串截斷。"""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"...(截斷，共 {len(value)} 字元)"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value[:50]]
    return value


def log_action(event: str, **data: Any) -> None:
    """寫入一筆結構化動作紀錄，同時寫入文字日誌。"""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **_truncate(data),
    }
    get_logger("action").info("%s %s", event, json.dumps(record, ensure_ascii=False, default=str)[:1000])
    if _logs_dir is None:
        return
    path = _logs_dir / f"actions_{datetime.now():%Y%m%d}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
