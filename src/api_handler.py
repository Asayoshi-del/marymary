from __future__ import annotations

"""
X API Handler - X API v2 との通信を制御するモジュール
Tweepy を使用し、ツイート投稿・取得・検索を行う。
"""

import time
import logging
from typing import Optional

import tweepy
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)


class XAPIClient:
    """X API v2 クライアントラッパー"""

    def __init__(self):
        self.api_key = os.getenv("X_API_KEY")
        self.api_secret = os.getenv("X_API_SECRET")
        self.access_token = os.getenv("X_ACCESS_TOKEN")
        self.access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        self.bearer_token = os.getenv("X_BEARER_TOKEN")

        self._validate_credentials()

        # v2 Client（ツイート投稿・検索用）
        self.client = tweepy.Client(
            bearer_token=self.bearer_token,
            consumer_key=self.api_key,
            consumer_secret=self.api_secret,
            access_token=self.access_token,
            access_token_secret=self.access_token_secret,
            wait_on_rate_limit=True,
        )

        self.username = os.getenv("X_USERNAME", "3m6LGY8PTkQKx63")
        self._user_id: Optional[str] = None

    def _validate_credentials(self):
        """APIキーが全て設定されているか検証"""
        required = {
            "X_API_KEY": self.api_key,
            "X_API_SECRET": self.api_secret,
            "X_ACCESS_TOKEN": self.access_token,
            "X_ACCESS_TOKEN_SECRET": self.access_token_secret,
            "X_BEARER_TOKEN": self.bearer_token,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise ValueError(
                f"以下のAPIキーが .env に設定されていません: {', '.join(missing)}\n"
                f".env.example を参考に .env ファイルを作成してください。"
            )

    @property
    def user_id(self) -> str:
        """自分のユーザーIDを取得（キャッシュ付き）"""
        if self._user_id is None:
            user = self.client.get_user(username=self.username)
            if user.data:
                self._user_id = str(user.data.id)
            else:
                raise ValueError(f"ユーザー @{self.username} が見つかりません。")
        return self._user_id

    def post_tweet(self, text: str, reply_to_id: Optional[str] = None) -> dict:
        """
        ツイートを投稿する（返信も可能）。

        Args:
            text: 投稿テキスト（140文字以内）
            reply_to_id: 返信先のツイートID（任意）

        Returns:
            投稿結果の辞書
        """
        if len(text) > 140:
            raise ValueError(f"ツイートが140文字を超えています ({len(text)}文字)")

        try:
            response = self.client.create_tweet(
                text=text,
                in_reply_to_tweet_id=reply_to_id
            )
            tweet_id = response.data["id"]
            logger.info(f"ツイート投稿成功: ID={tweet_id}{' (Reply)' if reply_to_id else ''}")
            return {"success": True, "tweet_id": tweet_id, "text": text}
        except tweepy.TweepyException as e:
            logger.error(f"ツイート投稿失敗: {e}")
            return {"success": False, "error": str(e), "text": text}

    def get_mentions(self, since_id: Optional[str] = None, max_results: int = 10) -> list[dict]:
        """
        自分へのメンションを取得する。

        Args:
            since_id: このIDより後のメンションのみ取得
            max_results: 取得件数

        Returns:
            メンションのリスト
        """
        try:
            mentions = self.client.get_users_mentions(
                id=self.user_id,
                since_id=since_id,
                max_results=max_results,
                tweet_fields=["created_at", "author_id", "text", "conversation_id"],
                expansions=["author_id"],
            )

            if not mentions.data:
                return []

            # ユーザー情報のマッピング作成
            users = {str(u.id): u.username for u in mentions.includes["users"]} if mentions.includes else {}

            results = []
            for tweet in mentions.data:
                author_id = str(tweet.author_id)
                results.append({
                    "id": str(tweet.id),
                    "text": tweet.text,
                    "author_id": author_id,
                    "author_username": users.get(author_id, "unknown"),
                    "created_at": str(tweet.created_at) if tweet.created_at else None,
                    "conversation_id": str(tweet.conversation_id) if tweet.conversation_id else None,
                })
            
            logger.info(f"メンション {len(results)} 件取得完了")
            return results
        except tweepy.TweepyException as e:
            logger.error(f"メンション取得失敗: {e}")
            return []

    def get_user_tweets(self, max_results: int = 50) -> list[dict]:
        """
        自分の過去ツイートを取得する。

        Args:
            max_results: 取得件数（最大100）

        Returns:
            ツイートのリスト
        """
        try:
            tweets = self.client.get_users_tweets(
                id=self.user_id,
                max_results=min(max_results, 100),
                tweet_fields=["created_at", "public_metrics", "text"],
            )
            if not tweets.data:
                logger.warning("ツイートが見つかりませんでした。")
                return []

            results = []
            for tweet in tweets.data:
                results.append(
                    {
                        "id": str(tweet.id),
                        "text": tweet.text,
                        "created_at": str(tweet.created_at) if tweet.created_at else None,
                        "metrics": tweet.public_metrics if tweet.public_metrics else {},
                    }
                )
            logger.info(f"過去ツイート {len(results)} 件取得完了")
            return results
        except tweepy.TweepyException as e:
            logger.error(f"ツイート取得失敗: {e}")
            return []

    def search_tweets(
        self, query: str, max_results: int = 20, sort_order: str = "relevancy"
    ) -> list[dict]:
        """
        ツイートを検索する（X API Basicプラン以上が必要）。

        Args:
            query: 検索クエリ
            max_results: 取得件数（10-100）
            sort_order: ソート順（"relevancy" or "recency"）

        Returns:
            検索結果のツイートリスト
        """
        try:
            tweets = self.client.search_recent_tweets(
                query=query,
                max_results=max(10, min(max_results, 100)),
                tweet_fields=["created_at", "public_metrics", "author_id", "text"],
                sort_order=sort_order,
            )

            if not tweets.data:
                logger.info(f"検索結果なし: {query}")
                return []

            results = []
            for tweet in tweets.data:
                metrics = tweet.public_metrics or {}
                results.append(
                    {
                        "id": str(tweet.id),
                        "text": tweet.text,
                        "author_id": str(tweet.author_id) if tweet.author_id else None,
                        "created_at": str(tweet.created_at) if tweet.created_at else None,
                        "like_count": metrics.get("like_count", 0),
                        "retweet_count": metrics.get("retweet_count", 0),
                        "reply_count": metrics.get("reply_count", 0),
                        "impression_count": metrics.get("impression_count", 0),
                    }
                )

            # エンゲージメント順にソート
            results.sort(
                key=lambda x: x["like_count"] + x["retweet_count"] * 2, reverse=True
            )
            logger.info(f"検索完了: {query} → {len(results)} 件")
            return results

        except tweepy.errors.Forbidden as e:
            logger.warning(
                f"検索APIアクセス不可（プラン制限の可能性）: {e}"
            )
            return []
        except tweepy.TweepyException as e:
            logger.error(f"検索失敗: {e}")
            return []

    def get_user_by_username(self, username: str) -> Optional[dict]:
        """ユーザー名からユーザー情報を取得"""
        try:
            user = self.client.get_user(
                username=username,
                user_fields=["public_metrics", "description"],
            )
            if user.data:
                return {
                    "id": str(user.data.id),
                    "username": user.data.username,
                    "name": user.data.name,
                    "description": user.data.description,
                    "metrics": user.data.public_metrics,
                }
            return None
        except tweepy.TweepyException as e:
            logger.error(f"ユーザー取得失敗 @{username}: {e}")
            return None
