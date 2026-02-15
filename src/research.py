from __future__ import annotations

"""
Research Module - バズ投稿のリサーチ・分析モジュール
指定ジャンルでバズっている投稿を取得・分析し、構造パターンを抽出する。
"""

import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# リサーチ対象ジャンルとキーワード
RESEARCH_GENRES = {
    "AIマネタイズ": [
        "AI 副業 稼ぐ",
        "ChatGPT マネタイズ",
        "Claude 活用法",
        "AIツール 収益化",
        "自動化 ビジネス",
    ],
    "AIトレンド": [
        "最新AIニュース",
        "Gemini アップデート",
        "生成AI 未来",
        "AI 仕事 変化",
        "シンギュラリティ",
    ],
    "自己啓発×AI": [
        "AI 学習法",
        "リスキリング AI",
        "AI時代 スキル",
        "生産性向上 ツール",
        "人生変える AI",
    ],
    "エンジニアリング": [
        "プログラミング AI",
        "ノーコード 開発",
        "個人開発 成功",
        "技術トレンド",
        "エンジニア キャリア",
    ],
}

# バズの基準（最低いいね数）
BUZZ_THRESHOLD_LIKES = 100


class ResearchModule:
    """バズ投稿のリサーチ・分析"""

    def __init__(self, api_client):
        """
        Args:
            api_client: XAPIClient インスタンス
        """
        self.api = api_client
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)

    def research_genre(self, genre: str, max_per_keyword: int = 10) -> list[dict]:
        """
        指定ジャンルのバズ投稿をリサーチする。

        Args:
            genre: ジャンル名（RESEARCH_GENRES のキー）
            max_per_keyword: キーワードごとの最大取得件数

        Returns:
            バズ投稿のリスト
        """
        keywords = RESEARCH_GENRES.get(genre, [])
        if not keywords:
            logger.warning(f"未定義のジャンル: {genre}")
            return []

        all_tweets = []
        for keyword in keywords:
            # RT・リプライを除外し、日本語のみを検索
            query = f"{keyword} lang:ja -is:retweet -is:reply"
            tweets = self.api.search_tweets(query=query, max_results=max_per_keyword)
            all_tweets.extend(tweets)
            logger.info(f"[{genre}] '{keyword}' → {len(tweets)} 件取得")

        # バズ基準を満たすもののみ抽出
        buzz_tweets = [
            t for t in all_tweets if t.get("like_count", 0) >= BUZZ_THRESHOLD_LIKES
        ]

        # 重複除去（IDベース）
        seen_ids = set()
        unique_tweets = []
        for t in buzz_tweets:
            if t["id"] not in seen_ids:
                seen_ids.add(t["id"])
                t["genre"] = genre
                unique_tweets.append(t)

        logger.info(
            f"[{genre}] バズ投稿 {len(unique_tweets)} 件抽出（閾値: {BUZZ_THRESHOLD_LIKES}いいね）"
        )
        return unique_tweets

    def research_all_genres(self) -> list[dict]:
        """全ジャンルをリサーチする"""
        all_results = []
        for genre in RESEARCH_GENRES:
            results = self.research_genre(genre)
            all_results.extend(results)
        return all_results

    def analyze_buzz_patterns(self, tweets: list[dict]) -> dict:
        """
        バズ投稿の構造パターンを分析する。

        Args:
            tweets: バズ投稿リスト

        Returns:
            分析結果の辞書
        """
        if not tweets:
            return {"patterns": [], "avg_length": 0, "top_tweets": []}

        # テキスト長の分析
        lengths = [len(t["text"]) for t in tweets]
        avg_length = sum(lengths) / len(lengths)

        # 構造パターンの抽出
        patterns = []
        for tweet in tweets:
            text = tweet["text"]
            pattern = self._detect_pattern(text)
            if pattern:
                patterns.append(pattern)

        # パターンの集計
        pattern_counts = {}
        for p in patterns:
            pattern_counts[p] = pattern_counts.get(p, 0) + 1

        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)

        # トップバズ投稿
        top_tweets = sorted(
            tweets, key=lambda x: x.get("like_count", 0), reverse=True
        )[:10]

        analysis = {
            "total_analyzed": len(tweets),
            "avg_length": round(avg_length, 1),
            "patterns": sorted_patterns[:5],
            "top_tweets": [
                {"text": t["text"], "likes": t.get("like_count", 0)} for t in top_tweets
            ],
        }

        logger.info(f"バズパターン分析完了: {len(tweets)} 件 → {len(sorted_patterns)} パターン")
        return analysis

    def _detect_pattern(self, text: str) -> Optional[str]:
        """テキストの構造パターンを検出する"""
        # 問いかけ型
        if text.endswith("？") or text.endswith("?"):
            return "問いかけ型"
        # 断言型
        if text.endswith("。") and any(w in text for w in ["べき", "しかない", "それだけ"]):
            return "断言型"
        # リスト型
        if any(c in text for c in ["①", "②", "１", "２", "・"]):
            return "リスト型"
        # 対比型
        if any(w in text for w in ["しかし", "でも", "一方で", "ところが"]):
            return "対比型"
        # 体験型
        if any(w in text for w in ["私は", "僕は", "実際に", "経験上"]):
            return "体験型"
        # 格言型
        if len(text) < 60 and text.endswith("。"):
            return "格言型"
        return "その他"

    def save_research_results(self, results: list[dict], filename: str = "research_results.json"):
        """リサーチ結果を保存"""
        filepath = os.path.join(self.data_dir, filename)
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_count": len(results),
            "tweets": results,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"リサーチ結果保存: {filepath}")

    def load_research_results(self, filename: str = "research_results.json") -> list[dict]:
        """保存済みリサーチ結果を読み込み"""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            logger.warning(f"リサーチ結果ファイルなし: {filepath}")
            return []
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tweets", [])

    def get_sample_buzz_tweets(self) -> list[dict]:
        """
        APIアクセスなしで使えるサンプルバズ投稿（デモ・テスト用）。
        X API Freeプランで検索が制限される場合のフォールバック。
        """
        return [
            {
                "text": "AIに仕事を奪われる人と、AIを使って仕事を効率化する人の差は「好奇心」だけです。新しいツールを触ることを恐れないでください。",
                "like_count": 5200,
                "genre": "AIマネタイズ",
            },
            {
                "text": "Claude 3.5 Sonnetのコーディング能力が異次元すぎる。エンジニアはコードを書く時間より、設計とレビューに時間を使うべき時代になった。",
                "like_count": 3800,
                "genre": "AIトレンド",
            },
            {
                "text": "副業で月5万稼ぐなら、プログラミングより「AI×コンテンツ制作」が一番早い。誰でもクリエイターになれる時代が来ました。",
                "like_count": 2100,
                "genre": "AIマネタイズ",
            },
            {
                "text": "「AIは人間味がない」というのは誤解です。使い手の感情や意図をどれだけプロンプトに乗せられるかで、出力される文章の温度感は劇的に変わります。",
                "like_count": 6500,
                "genre": "AIトレンド",
            },
            {
                "text": "人生を変えるのに必要なのは、才能ではなく「環境」と「ツール」です。最新のAIツールを使いこなすだけで、個人の生産性は10倍になります。",
                "like_count": 4200,
                "genre": "自己啓発×AI",
            },
        ]
