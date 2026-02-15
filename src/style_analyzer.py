"""
Style Analyzer - 過去ツイートのスタイル分析モジュール
語尾パターン、漢字/ひらがな比率、口癖、リズムパターンを分析する。
"""

import json
import logging
import os
import re
import unicodedata
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)


class StyleAnalyzer:
    """過去ツイートのスタイル分析"""

    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self._analysis_cache: Optional[dict] = None

    def analyze_tweets(self, tweets: list[dict]) -> dict:
        """
        ツイートリストを分析し、スタイルプロファイルを生成する。

        Args:
            tweets: {"text": "...", ...} のリスト

        Returns:
            スタイルプロファイル辞書
        """
        texts = [t["text"] for t in tweets if t.get("text")]
        if not texts:
            logger.warning("分析対象ツイートがありません。")
            return self._default_profile()

        profile = {
            "total_tweets_analyzed": len(texts),
            "endings": self._analyze_endings(texts),
            "char_ratios": self._analyze_char_ratios(texts),
            "frequent_phrases": self._analyze_phrases(texts),
            "avg_length": round(sum(len(t) for t in texts) / len(texts), 1),
            "length_distribution": self._analyze_length_distribution(texts),
            "tone_markers": self._analyze_tone(texts),
        }

        self._analysis_cache = profile
        logger.info(
            f"スタイル分析完了: {len(texts)} 件, 平均長 {profile['avg_length']} 文字"
        )
        return profile

    def _analyze_endings(self, texts: list[str]) -> list[tuple[str, int]]:
        """語尾パターンを分析"""
        endings = []
        # 文末パターンを抽出
        ending_patterns = [
            (r"である。?$", "である"),
            (r"だ。?$", "だ"),
            (r"です。?$", "です"),
            (r"ます。?$", "ます"),
            (r"だろう。?$", "だろう"),
            (r"ない。?$", "ない"),
            (r"する。?$", "する"),
            (r"こと。?$", "こと"),
            (r"もの。?$", "もの"),
            (r"たい。?$", "たい"),
            (r"べきだ。?$", "べきだ"),
            (r"しかない。?$", "しかない"),
            (r"のだ。?$", "のだ"),
            (r"いる。?$", "いる"),
            (r"れる。?$", "れる"),
        ]

        for text in texts:
            # 文を分割して各文末を分析
            sentences = re.split(r"[。！？\n]", text)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) < 3:
                    continue
                for pattern, label in ending_patterns:
                    if re.search(pattern, sentence):
                        endings.append(label)
                        break

        counter = Counter(endings)
        total = sum(counter.values()) or 1
        return [
            (ending, count, round(count / total * 100, 1))
            for ending, count in counter.most_common(10)
        ]

    def _analyze_char_ratios(self, texts: list[str]) -> dict:
        """漢字/ひらがな/カタカナ/記号の比率を計算"""
        kanji = 0
        hiragana = 0
        katakana = 0
        other = 0
        total = 0

        for text in texts:
            for char in text:
                if char.isspace():
                    continue
                total += 1
                name = unicodedata.name(char, "")
                if "CJK UNIFIED IDEOGRAPH" in name:
                    kanji += 1
                elif "HIRAGANA" in name:
                    hiragana += 1
                elif "KATAKANA" in name:
                    katakana += 1
                else:
                    other += 1

        total = total or 1
        return {
            "kanji_pct": round(kanji / total * 100, 1),
            "hiragana_pct": round(hiragana / total * 100, 1),
            "katakana_pct": round(katakana / total * 100, 1),
            "other_pct": round(other / total * 100, 1),
        }

    def _analyze_phrases(self, texts: list[str]) -> list[tuple[str, int]]:
        """頻出フレーズ（口癖）を抽出"""
        # 2-5文字のn-gramを抽出
        all_ngrams = []
        for text in texts:
            clean = re.sub(r"https?://\S+", "", text)
            clean = re.sub(r"@\w+", "", clean)
            for n in range(2, 6):
                for i in range(len(clean) - n + 1):
                    ngram = clean[i : i + n]
                    if not re.match(r"^[\s\u3000]+$", ngram):  # 空白のみは除外
                        all_ngrams.append(ngram)

        counter = Counter(all_ngrams)
        # 3回以上出現するフレーズのみ
        frequent = [
            (phrase, count)
            for phrase, count in counter.most_common(30)
            if count >= 3
            and not re.match(r"^[。、！？\s]+$", phrase)  # 句読点のみは除外
        ]
        return frequent[:15]

    def _analyze_length_distribution(self, texts: list[str]) -> dict:
        """文字数の分布を分析"""
        lengths = [len(t) for t in texts]
        return {
            "min": min(lengths),
            "max": max(lengths),
            "avg": round(sum(lengths) / len(lengths), 1),
            "under_70": sum(1 for l in lengths if l < 70),
            "70_to_100": sum(1 for l in lengths if 70 <= l < 100),
            "100_to_140": sum(1 for l in lengths if 100 <= l <= 140),
        }

    def _analyze_tone(self, texts: list[str]) -> dict:
        """口調の特徴を分析"""
        markers = {
            "assertive": 0,  # 断定的
            "questioning": 0,  # 問いかけ
            "reflective": 0,  # 内省的
            "instructive": 0,  # 教え
        }

        for text in texts:
            if any(w in text for w in ["べき", "しかない", "絶対", "確実に"]):
                markers["assertive"] += 1
            if "？" in text or "?" in text:
                markers["questioning"] += 1
            if any(w in text for w in ["思う", "感じる", "気づいた", "考える"]):
                markers["reflective"] += 1
            if any(w in text for w in ["すべき", "してほしい", "おすすめ", "大切"]):
                markers["instructive"] += 1

        total = len(texts) or 1
        return {k: round(v / total * 100, 1) for k, v in markers.items()}

    def _default_profile(self) -> dict:
        """デフォルトのスタイルプロファイル（AI戦略家・断定調）"""
        return {
            "total_tweets_analyzed": 0,
            "endings": [
                ("だ", 0, 40.0),
                ("である", 0, 30.0),
                ("だろう", 0, 10.0),
                ("ない", 0, 15.0),
                ("する", 0, 5.0),
            ],
            "char_ratios": {
                "kanji_pct": 40.0,
                "hiragana_pct": 45.0,
                "katakana_pct": 10.0,
                "other_pct": 5.0,
            },
            "frequent_phrases": [],
            "avg_length": 120,
            "length_distribution": {"min": 80, "max": 140, "avg": 120},
            "tone_markers": {
                "assertive": 60.0,
                "questioning": 5.0,
                "reflective": 15.0,
                "instructive": 20.0,
            },
            "note": "デフォルトプロファイル（AI戦略家・断定調）",
        }

    def get_style_prompt_fragment(self, profile: Optional[dict] = None) -> str:
        """
        スタイルプロファイルをLLMプロンプト用のテキストに変換する。

        Args:
            profile: スタイルプロファイル（Noneの場合はキャッシュを使用）

        Returns:
            プロンプトに挿入するスタイル指示テキスト
        """
        p = profile or self._analysis_cache or self._default_profile()

        # 語尾パターンの上位を抽出
        top_endings = [f"「{e[0]}」({e[2]}%)" for e in p.get("endings", [])[:5]]
        endings_str = "、".join(top_endings) if top_endings else "「だ」「である」調"

        # 文字比率
        ratios = p.get("char_ratios", {})
        kanji_pct = ratios.get("kanji_pct", 35)
        hiragana_pct = ratios.get("hiragana_pct", 45)

        # 口癖
        phrases = p.get("frequent_phrases", [])
        phrase_examples = "、".join([f"「{ph[0]}」" for ph in phrases[:5]]) if phrases else "なし"

        # トーン
        tone = p.get("tone_markers", {})
        dominant_tone = max(tone, key=tone.get) if tone else "reflective"
        tone_desc = {
            "assertive": "断定的で力強い",
            "questioning": "問いかけ型で読者に考えさせる",
            "reflective": "内省的で落ち着いた",
            "instructive": "教訓的でアドバイス寄り",
        }.get(dominant_tone, "バランスの取れた")

        return f"""【文体ルール】
- 語尾パターン: {endings_str}
- 漢字率約{kanji_pct}%、ひらがな率約{hiragana_pct}%のバランスを保つ
- 口調は{tone_desc}トーン
- 頻出フレーズ: {phrase_examples}
- 平均文字数: {p.get('avg_length', 100)}文字前後"""

    def save_profile(self, profile: dict, filename: str = "style_profile.json"):
        """スタイルプロファイルを保存"""
        filepath = os.path.join(self.data_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        logger.info(f"スタイルプロファイル保存: {filepath}")

    def load_profile(self, filename: str = "style_profile.json") -> Optional[dict]:
        """保存済みスタイルプロファイルを読み込み"""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            profile = json.load(f)
        self._analysis_cache = profile
        return profile
