import logging
import time
from typing import List

logger = logging.getLogger(__name__)

class EngagementHandler:
    """エゴサ・エンゲージメント（いいね等）を管理するクラス"""

    def __init__(self, api_client):
        self.api = api_client
        self.keywords = [
            "AIエージェント",
            "AIツール"
        ]

    def run_ego_search_and_like(self, max_per_keyword: int = 5, dry_run: bool = False):
        """キーワードで検索していいねをする"""
        logger.info(f"エゴサ開始: キーワード={self.keywords}")
        
        for kw in self.keywords:
            logger.info(f"キーワード「{kw}」で検索中...")
            # 最新の投稿を検索
            tweets = self.api.search_tweets(query=kw, max_results=10, sort_order="recency")
            
            if not tweets:
                continue

            count = 0
            for tweet in tweets:
                if count >= max_per_keyword:
                    break
                
                # 自分の投稿はスキップ
                if tweet.get("author_id") == self.api.user_id:
                    continue

                if dry_run:
                    logger.info(f"[DRY RUN] いいね予定: ID={tweet['id']} Text={tweet['text'][:30]}...")
                    count += 1
                else:
                    success = self.api.like_tweet(tweet["id"])
                    if success:
                        count += 1
                        time.sleep(1) # レート制限対策の微小待機

            logger.info(f"キーワード「{kw}」で {count} 件にいいねしました")
