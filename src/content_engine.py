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
PERSONA = """あなたは「次世代の生き方を提唱するAI戦略家」です。
以下の属性を持っています：
- 最先端のAI技術（Claude, GPT, Gemini, OpenSource）に精通している
- 「AIを使って人生をどう変えるか」「どう稼ぐか」という実利的な視点を重視する
- 読者に媚びず、本質的で耳の痛いこともズバッと言う
- 口調は「だ・である」調（断定形）で統一する。質問形や「〜しましょう」といった呼びかけは避ける
- 感情的な装飾を排し、論理と洞察で語る"""

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
        user_thoughts: str | None = None,
        max_retries: int = 3,
    ) -> str:
        """
        ツイートを1件生成する。

        Args:
            theme: 投稿テーマ（空の場合はランダム選択）
            reference_tweets: 参考にするバズ投稿テキストリスト
            user_thoughts: ユーザーの思考メモ（最優先で使用）
            max_retries: 文字数超過時のリトライ回数

        Returns:
            生成されたツイートテキスト
        """
        if not theme and not user_thoughts:
            import random
            theme = random.choice(CONTENT_THEMES)

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(theme, reference_tweets, user_thoughts)

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
                    source = "思考メモ" if user_thoughts else f"テーマ: {theme}"
                    logger.info(
                        f"ツイート生成成功 ({len(tweet_text)}文字, {source})"
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

    def generate_reply(
        self,
        mention_text: str,
        author_username: str,
        context_tweets: list[str] | None = None
    ) -> str:
        """
        メンションに対する返信を生成する。

        Args:
            mention_text: 相手の投稿テキスト
            author_username: 相手のユーザーネーム
            context_tweets: 会話の文脈（あれば）

        Returns:
            返信テキスト
        """
        system_prompt = f"""{PERSONA}

【返信のルール】
1. 相手の言葉に対して、鋭い洞察や有益なアドバイス（AI戦略家として）を返すこと
2. 媚びたり、当たり障りのない挨拶だけで終わらせないこと
3. 「だ・である」調を維持し、100文字〜130文字程度で密度を高めること
4. 相手のユーザー名（@{author_username}）を文頭に含めること
5. ハッシュタグ、URLは含めない
"""
        user_prompt = f"以下のユーザーからの投稿に対して、返信を1件作成してください。\n\n【相手の投稿】\n@{author_username}: {mention_text}"
        
        if context_tweets:
            user_prompt += "\n\n【会話の以前の流れ】\n" + "\n".join(context_tweets)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.7,
            )
            reply_text = response.content[0].text.strip()
            return self._clean_output(reply_text)
        except Exception as e:
            logger.error(f"返信生成失敗: {e}")
            raise

    def generate_batch(
        self,
        count: int = 10,
        reference_tweets: list[str] | None = None,
        user_thoughts: str | None = None,
    ) -> list[str]:
        """
        複数のツイートを一括生成する。
        user_thoughtsがある場合は、内容の重複を避けるために一括でプロンプトを送り、
        多様な視点から生成させる。

        Args:
            count: 生成件数
            reference_tweets: 参考バズ投稿リスト
            user_thoughts: ユーザーの思考メモ

        Returns:
            生成されたツイートリスト
        """
        if user_thoughts:
            return self._generate_varied_batch_from_thoughts(count, reference_tweets, user_thoughts)

        # 通常のテーマベース生成（ループ）
        import random
        tweets = []
        themes = random.sample(CONTENT_THEMES, min(count, len(CONTENT_THEMES)))
        while len(themes) < count:
            themes.append(random.choice(CONTENT_THEMES))

        for i, theme in enumerate(themes):
            try:
                tweet = self.generate_tweet(
                    theme=theme,
                    reference_tweets=reference_tweets,
                    user_thoughts=None,
                )
                tweets.append(tweet)
                logger.info(f"バッチ生成 [{i + 1}/{count}] 完了")
            except Exception as e:
                logger.error(f"バッチ生成 [{i + 1}/{count}] 失敗: {e}")
                continue
        return tweets

    def _generate_varied_batch_from_thoughts(
        self, count: int, reference_tweets: list[str] | None, user_thoughts: str
    ) -> list[str]:
        """思考メモから、重複のない多様なツイートを生成する"""
        system_prompt = self._build_system_prompt()
        
        user_prompt = f"""以下の【ユーザーの思考メモ】を読み込み、内容が重複しないように {count} 件の異なる投稿を作成してください。

【戦略】
1. メモの中の異なるセクション、異なる視点、異なるエピソードに焦点を当てて、1つずつ独立した投稿にすること。
2. 全体として1つのストーリーにするのではなく、それぞれが単体で完結する「強い」投稿にすること。
3. すべて「だ・である」調の断定形で、ペルソナ（AI戦略家）らしい鋭い洞察を含めること。

【ユーザーの思考メモ】
{user_thoughts}
"""
        if reference_tweets:
            user_prompt += "\n【構造の参考】\n"
            for i, ref in enumerate(reference_tweets[:2], 1):
                user_prompt += f"参考{i}: {ref}\n"

        user_prompt += f"\n出力形式：\n1. [投稿テキスト]\n2. [投稿テキスト]\n...(合計 {count} 件)"

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.7,
            )

            raw_output = response.content[0].text.strip()
            # 番号付きリストを分割
            items = re.split(r"\n\d+[\.\)]\s*", "\n" + raw_output)
            tweets = [self._clean_output(it.strip()) for it in items if it.strip()]
            
            # バリデーション済みのものだけ採用
            valid_tweets = []
            for t in tweets:
                is_valid, _ = self.validate_tweet(t)
                if is_valid:
                    valid_tweets.append(t)
            
            # 足りない場合は個別に補完（再帰はせず、テーマなしで生成）
            while len(valid_tweets) < count:
                try:
                    t = self.generate_tweet(user_thoughts=user_thoughts)
                    valid_tweets.append(t)
                except:
                    break
            
            return valid_tweets[:count]

        except Exception as e:
            logger.error(f"多様なバッチ生成に失敗: {e}")
            return []

    def _build_system_prompt(self) -> str:
        """システムプロンプトを構築"""
        prompt = f"""{PERSONA}

【絶対ルール】
1. 110文字〜135文字程度で、内容の濃い投稿テキストを出力すること
2. ハッシュタグ（#）は絶対に使用しない
3. 投資助言に該当する断定的表現は避ける（「買い」「売り」「必ず儲かる」等は禁止）
4. 思考法やトレンドの紹介に留め、具体的な銘柄推奨はしない
5. URLやメンションは含めない

{self.style_prompt}"""
        return prompt

    def _build_user_prompt(
        self, theme: str, reference_tweets: list[str] | None, user_thoughts: str | None
    ) -> str:
        """ユーザープロンプトを構築"""
        prompt = ""

        if user_thoughts:
            prompt += f"以下の【ユーザーが今考えていること・伝えたいこと】を最優先で反映し、投稿を作成してください。\n"
            prompt += f"この内容を、ペルソナ（AI戦略家）の視点で深掘り・昇華させてください。\n\n"
            prompt += f"【ユーザーの思考メモ】\n{user_thoughts}\n\n"
        
        prompt += f"以下のテーマ（切り口）も参考にしてください。\nテーマ: {theme}\n"

        if reference_tweets:
            prompt += "\n【参考にすべきバズ投稿の構造・リズム】\n"
            for i, ref in enumerate(reference_tweets[:3], 1):
                prompt += f"参考{i}: {ref}\n"
            prompt += "\n上記のバズ投稿の構造やリズムを参考にしつつ、独自の内容を生成してください。\n"

        prompt += "\n投稿テキストのみを出力してください（120文字前後を目指してください）。"
        return prompt

    def _clean_output(self, text: str) -> str:
        """LLM出力のクリーニング"""
        # 前後の引用符を除去
        text = text.strip('"\'「」『』')
        # マークダウンの記号を除去
        text = re.sub(r"^\*+|\*+$", "", text)
        # 先頭の番号を除去
        text = re.sub(r"^\d+[\.\)]\s*", "", text)
        # 複数行の場合は改行を維持しつつ連結
        if "\n" in text:
             return text.strip()
        return text.strip()

    def validate_tweet(self, text: str) -> tuple[bool, str]:
        """
        ツイートのバリデーション。

        Returns:
            (is_valid, issue_description)
        """
        # 文字数チェック
        length = len(text)
        if length > 140:
            return False, f"文字数超過 ({length}文字)"
        if length < 60:
            return False, f"文字数不足 ({length}文字) - もっと内容を充実させてください"

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
