"""
Scheduler - 予約投稿の時間分散管理モジュール
1日10件の投稿をピークタイムに分散配置して実行する。
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ピークタイムスロット（JST）
# 朝3件、昼3件、夜4件 = 計10件
PEAK_SLOTS = [
    {"time": "07:00", "period": "morning"},
    {"time": "08:00", "period": "morning"},
    {"time": "09:00", "period": "morning"},
    {"time": "12:00", "period": "noon"},
    {"time": "12:30", "period": "noon"},
    {"time": "13:00", "period": "noon"},
    {"time": "20:00", "period": "evening"},
    {"time": "21:00", "period": "evening"},
    {"time": "22:00", "period": "evening"},
    {"time": "23:00", "period": "evening"},
]


class PostScheduler:
    """予約投稿の時間分散管理"""

    def __init__(self, api_client=None):
        """
        Args:
            api_client: XAPIClient インスタンス（Noneの場合はドライラン）
        """
        self.api = api_client
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.scheduled_file = os.path.join(self.data_dir, "scheduled.json")
        self.history_file = os.path.join(self.data_dir, "post_history.json")

    def stock_tweets(self, tweets: list[str]):
        """
        生成されたツイートを予約ストックに追加する。

        Args:
            tweets: ツイートテキストのリスト
        """
        existing = self._load_scheduled()

        for tweet in tweets:
            existing.append(
                {
                    "text": tweet,
                    "status": "pending",
                    "created_at": datetime.now().isoformat(),
                    "posted_at": None,
                }
            )

        self._save_scheduled(existing)
        logger.info(f"ツイート {len(tweets)} 件をストックに追加（合計: {len(existing)} 件）")

    def get_pending_tweets(self, count: int = 10) -> list[dict]:
        """未投稿のツイートを取得"""
        scheduled = self._load_scheduled()
        pending = [s for s in scheduled if s["status"] == "pending"]
        return pending[:count]

    def assign_time_slots(self, tweets: list[dict]) -> list[dict]:
        """
        ツイートにピークタイムスロットを割り当てる。

        Args:
            tweets: 予約ツイートリスト

        Returns:
            タイムスロットが割り当てられたリスト
        """
        today = datetime.now().date()
        slots = PEAK_SLOTS[: len(tweets)]

        for i, tweet in enumerate(tweets):
            if i < len(slots):
                slot = slots[i]
                hour, minute = map(int, slot["time"].split(":"))
                scheduled_time = datetime.combine(
                    today, datetime.min.time().replace(hour=hour, minute=minute)
                )
                # 既に過ぎた時間は翌日に設定
                if scheduled_time <= datetime.now():
                    scheduled_time += timedelta(days=1)
                tweet["scheduled_time"] = scheduled_time.isoformat()
                tweet["period"] = slot["period"]

        return tweets

    def execute_scheduled(self, dry_run: bool = False) -> list[dict]:
        """
        時間が来た予約投稿を実行する。

        Args:
            dry_run: True の場合、実際に投稿しない

        Returns:
            実行結果のリスト
        """
        scheduled = self._load_scheduled()
        now = datetime.now()
        results = []

        for item in scheduled:
            if item["status"] != "pending":
                continue
            if "scheduled_time" not in item:
                continue

            scheduled_time = datetime.fromisoformat(item["scheduled_time"])
            if scheduled_time <= now:
                if dry_run:
                    logger.info(f"[DRY RUN] 投稿: {item['text'][:50]}...")
                    item["status"] = "dry_run"
                    results.append({"text": item["text"], "result": "dry_run"})
                else:
                    if self.api:
                        result = self.api.post_tweet(item["text"])
                        if result["success"]:
                            item["status"] = "posted"
                            item["posted_at"] = now.isoformat()
                            item["tweet_id"] = result["tweet_id"]
                            logger.info(f"投稿完了: {item['text'][:50]}...")
                        else:
                            item["status"] = "failed"
                            item["error"] = result["error"]
                            logger.error(f"投稿失敗: {result['error']}")
                        results.append({"text": item["text"], "result": result})
                    else:
                        logger.warning("APIクライアントが設定されていません。")
                        item["status"] = "no_api"

        self._save_scheduled(scheduled)
        self._update_history(results)
        return results

    def run_daemon(self, dry_run: bool = False):
        """
        デーモンモードで予約投稿を監視・実行する。

        Args:
            dry_run: ドライランモード
        """
        logger.info("スケジューラーデーモン起動...")
        logger.info(f"ドライラン: {'ON' if dry_run else 'OFF'}")

        try:
            while True:
                self.execute_scheduled(dry_run=dry_run)
                time.sleep(60)  # 1分ごとにチェック
        except KeyboardInterrupt:
            logger.info("スケジューラーデーモン停止")

    def get_schedule_summary(self) -> str:
        """現在のスケジュール状況を要約テキストで返す"""
        scheduled = self._load_scheduled()
        pending = [s for s in scheduled if s["status"] == "pending"]
        posted = [s for s in scheduled if s["status"] == "posted"]
        failed = [s for s in scheduled if s["status"] == "failed"]

        lines = [
            f"📊 スケジュール状況",
            f"  待機中: {len(pending)} 件",
            f"  投稿済: {len(posted)} 件",
            f"  失敗:   {len(failed)} 件",
            f"  合計:   {len(scheduled)} 件",
        ]

        if pending:
            lines.append("\n⏰ 次の予約投稿:")
            for item in pending[:3]:
                t = item.get("scheduled_time", "未設定")
                lines.append(f"  {t}: {item['text'][:40]}...")

        return "\n".join(lines)

    def clear_completed(self):
        """投稿済みのアイテムをクリアする"""
        scheduled = self._load_scheduled()
        remaining = [s for s in scheduled if s["status"] == "pending"]
        cleared = len(scheduled) - len(remaining)
        self._save_scheduled(remaining)
        logger.info(f"投稿済み {cleared} 件をクリア")

    def _load_scheduled(self) -> list[dict]:
        """スケジュールファイルを読み込み"""
        if not os.path.exists(self.scheduled_file):
            return []
        with open(self.scheduled_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_scheduled(self, data: list[dict]):
        """スケジュールファイルを保存"""
        with open(self.scheduled_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _update_history(self, results: list[dict]):
        """投稿履歴を更新"""
        history = []
        if os.path.exists(self.history_file):
            with open(self.history_file, "r", encoding="utf-8") as f:
                history = json.load(f)

        for r in results:
            history.append(
                {
                    "text": r["text"],
                    "timestamp": datetime.now().isoformat(),
                    "result": str(r.get("result", "")),
                }
            )

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
