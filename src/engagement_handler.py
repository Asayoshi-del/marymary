import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)

class EngagementHandler:
    """エゴサ・エンゲージメント（いいね・引用RT等）を管理するクラス"""

    def __init__(self, api_client, content_engine=None):
        self.api = api_client
        self.engine = content_engine
        self.keywords = [
            "AIエージェント",
            "AIツール"
        ]
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.state_file = os.path.join(self.data_dir, "engagement_state.json")

    def run_ego_search_and_like(self, max_per_keyword: int = 5, dry_run: bool = False):
        """キーワードで検索していいねをする"""
        if not self.api:
            logger.warning("APIクライアントが設定されていないため、エゴサをスキップします。")
            return

        logger.info(f"エゴサ・いいね開始: キーワード={self.keywords}")
        
        for kw in self.keywords:
            logger.info(f"キーワード「{kw}」で検索中...")
            tweets = self.api.search_tweets(query=kw, max_results=10, sort_order="recency")
            
            if not tweets:
                continue

            count = 0
            for tweet in tweets:
                if count >= max_per_keyword:
                    break
                
                if tweet.get("author_id") == self.api.user_id:
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] いいね予定: ID={tweet['id']} Text={tweet['text'][:30]}...")
                    count += 1
                else:
                    success = self.api.like_tweet(tweet["id"])
                    if success:
                        count += 1
                        time.sleep(1)

            logger.info(f"キーワード「{kw}」で {count} 件にいいねしました")

    def run_quote_retweet(self, dry_run: bool = False):
        """
        バズっている投稿や興味深い投稿を検索し、1件だけ引用RTする。
        乱用を避けるため、1時間に1回程度に制限する。
        """
        if not self.engine:
            logger.warning("ContentEngineが設定されていないため、引用RTをスキップします。")
            return
        
        if not self.api:
            logger.warning("APIクライアントが設定されていないため、引用RTをスキップします。")
            return

        state = self._load_state()
        last_qt_time = state.get("last_quote_time")
        
        # 3時間以内は連続で行わない（慎重な運用）
        if last_qt_time:
            last_dt = datetime.fromisoformat(last_qt_time)
            if datetime.now() - last_dt < timedelta(hours=3):
                logger.debug("最近引用RTを行ったため、今回はスキップします。")
                return

        logger.info("引用RT用の投稿を探索中...")
        # ターゲットキーワードから1つランダムに選ぶ、または「AI」などで広く検索
        # Basicプランでも使える標準的なクエリを使用
        target_kw = "(AIエージェント OR AIツール) lang:ja -is:retweet"
        tweets = self.api.search_tweets(query=target_kw, max_results=10)

        if not tweets:
            logger.info("引用RTに適した話題が見つかりませんでした。")
            return

        # 引用したことがない最新のものを1件選択
        quoted_ids = state.get("quoted_tweet_ids", [])
        target_tweet = None
        for t in tweets:
            if t["id"] not in quoted_ids and t.get("author_id") != self.api.user_id:
                target_tweet = t
                break

        if not target_tweet:
            return

        logger.info(f"引用RT生成中: ID={target_tweet['id']} Text={target_tweet['text'][:50]}...")
        comment = self.engine.generate_quote_comment(target_tweet["text"])

        if dry_run:
            logger.info(f"[DRY RUN] 引用RT投稿予定: {comment}")
        else:
            result = self.api.quote_tweet(text=comment, quote_tweet_id=target_tweet["id"])
            if result["success"]:
                logger.info(f"引用RT成功: ID={result['tweet_id']}")
                quoted_ids.append(target_tweet["id"])
                state["quoted_tweet_ids"] = quoted_ids[-50:] # 直近50件保持
                state["last_quote_time"] = datetime.now().isoformat()
                self._save_state(state)
            else:
                logger.error(f"引用RT失敗: {result.get('error')}")

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"quoted_tweet_ids": [], "last_quote_time": None}

    def _save_state(self, state: dict):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

