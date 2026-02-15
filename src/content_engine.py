from __future__ import annotations

"""
Content Engine - Claude APIを活用した投稿生成モジュール
ペルソナとスタイル分析に基づき、140文字以内の投稿案を生成する。
"""

import logging
import os
import re

import anthropic
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ペルソナ定義
PERSONA = """あなたは「次世代の生き方を提唱するAIマネタイズ専門家」です。
以下の属性を持っています：
- 最先端のAI技術（Claude, GPT, Gemini, OpenSource）に精通しているが、技術オタクではない
- 「AIを使って人生をどう変えるか」「どう稼ぐか」という実利的な視点を重視する
- 読者に「自分もできるかも」「人生が変わる予感がする」という希望を与える
- 口調は柔らかく丁寧だが、芯のある「です・ます」調（たまに「だ・である」を混ぜてリズムを作る）
- 読者に寄り添いつつ、行動を促すメンター的な存在"""

# 禁止表現（過度な煽りや投資助言回避）
BANNED_EXPRESSIONS = [
    "絶対に儲かる", "100%成功", "誰でも簡単", "何もしなくていい",
    "元本保証", "確実な利益", "裏技", "詐欺",
    "投資推奨", "買い時", "売り時",
]

# 投稿テーマカテゴリ
CONTENT_THEMES = [
    "AIツール（Claude Code, Antigravity, NotebookLM等）の活用法",
    "AI時代の新しい働き方・稼ぎ方",
    "AI副業による収益化のヒント",
    "テクノロジーを活用した自己変革・人生設計",
    "これからの時代に求められるスキルとマインド",
    "AIがもたらす社会変化と個人のチャンス",
    "AIを活用した時間術・生産性向上",
    "初心者でもできるAIスタートアップガイド",
]


class ContentEngine:
    """Claude APIを活用した投稿生成エンジン"""

    def __init__(self, style_prompt: str = ""):
        """
        Args:
            style_prompt: StyleAnalyzer から生成されたスタイル指示テキスト
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY が .env に設定されていません。"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.style_prompt = style_prompt
        self.model = "claude-sonnet-4-20250514"

    def generate_tweet(
        self,
        theme: str = "",
        reference_tweets: list[str] | None = None,
        max_retries: int = 3,
    ) -> str:
        """
        ツイートを1件生成する。

        Args:
            theme: 投稿テーマ（空の場合はランダム選択）
            reference_tweets: 参考にするバズ投稿テキストリスト
            max_retries: 文字数超過時のリトライ回数

        Returns:
            生成されたツイートテキスト
        """
        if not theme:
            import random
            theme = random.choice(CONTENT_THEMES)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(theme, reference_tweets)

        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=300,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    temperature=0.8,
                )

                tweet_text = response.content[0].text.strip()
                # 余計な引用符やマークダウンを除去
                tweet_text = self._clean_output(tweet_text)

                # バリデーション
                is_valid, issue = self.validate_tweet(tweet_text)
                if is_valid:
                    logger.info(
                        f"ツイート生成成功 ({len(tweet_text)}文字, テーマ: {theme})"
                    )
                    return tweet_text

                logger.warning(
                    f"バリデーション失敗 (attempt {attempt + 1}): {issue} → リトライ"
                )
                # リトライ時に文字数制限を強調
                user_prompt += f"\n\n※前回の生成では「{issue}」問題がありました。必ず140文字以内にしてください。"

            except anthropic.APIError as e:
                logger.error(f"Claude API エラー: {e}")
                raise

        raise ValueError(f"ツイート生成に{max_retries}回失敗しました。")

    def generate_batch(
        self,
        count: int = 10,
        reference_tweets: list[str] | None = None,
    ) -> list[str]:
        """
        複数のツイートを一括生成する。

        Args:
            count: 生成件数
            reference_tweets: 参考バズ投稿リスト

        Returns:
            生成されたツイートリスト
        """
        import random

        tweets = []
        themes = random.sample(CONTENT_THEMES, min(count, len(CONTENT_THEMES)))
        # 足りない分はランダムで追加
        while len(themes) < count:
            themes.append(random.choice(CONTENT_THEMES))

        for i, theme in enumerate(themes):
            try:
                tweet = self.generate_tweet(
                    theme=theme, reference_tweets=reference_tweets
                )
                tweets.append(tweet)
                logger.info(f"バッチ生成 [{i + 1}/{count}] 完了")
            except Exception as e:
                logger.error(f"バッチ生成 [{i + 1}/{count}] 失敗: {e}")
                continue

        return tweets

    def _build_system_prompt(self) -> str:
        """システムプロンプトを構築"""
        prompt = f"""{PERSONA}

【絶対ルール】
1. 必ず140文字以内で投稿テキストのみを出力すること（説明や注釈は不要）
2. ハッシュタグ（#）は絶対に使用しない
3. 投資助言に該当する断定的表現は避ける（「買い」「売り」「必ず儲かる」等は禁止）
4. 思考法やトレンドの紹介に留め、具体的な銘柄推奨はしない
5. URLやメンションは含めない

{self.style_prompt}"""
        return prompt

    def _build_user_prompt(
        self, theme: str, reference_tweets: list[str] | None
    ) -> str:
        """ユーザープロンプトを構築"""
        prompt = f"以下のテーマで、X（旧Twitter）の投稿テキストを1件だけ生成してください。\n\nテーマ: {theme}\n"

        if reference_tweets:
            prompt += "\n【参考にすべきバズ投稿の構造・リズム】\n"
            for i, ref in enumerate(reference_tweets[:3], 1):
                prompt += f"参考{i}: {ref}\n"
            prompt += "\n上記のバズ投稿の構造やリズムを参考にしつつ、独自の内容を生成してください。\n"

        prompt += "\n投稿テキストのみを出力してください（140文字以内、説明不要）。"
        return prompt

    def _clean_output(self, text: str) -> str:
        """LLM出力のクリーニング"""
        # 前後の引用符を除去
        text = text.strip('"\'「」『』')
        # マークダウンの記号を除去
        text = re.sub(r"^\*+|\*+$", "", text)
        # 先頭の番号を除去
        text = re.sub(r"^\d+[\.\)]\s*", "", text)
        # 複数行の場合は最初の行のみ
        if "\n" in text:
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            text = lines[0] if lines else text
        return text.strip()

    def validate_tweet(self, text: str) -> tuple[bool, str]:
        """
        ツイートのバリデーション。

        Returns:
            (is_valid, issue_description)
        """
        # 文字数チェック
        if len(text) > 140:
            return False, f"文字数超過 ({len(text)}文字)"
        if len(text) < 10:
            return False, f"文字数不足 ({len(text)}文字)"

        # ハッシュタグチェック
        if "#" in text or "＃" in text:
            return False, "ハッシュタグが含まれています"

        # 禁止表現チェック
        for expr in BANNED_EXPRESSIONS:
            if expr in text:
                return False, f"禁止表現「{expr}」が含まれています"

        # URLチェック
        if re.search(r"https?://", text):
            return False, "URLが含まれています"

        # メンションチェック
        if "@" in text:
            return False, "メンションが含まれています"

        return True, ""
