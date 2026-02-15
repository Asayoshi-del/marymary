"""
テスト - コンテンツエンジンとバリデーションのテスト
"""

import pytest
import sys
import os

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.content_engine import ContentEngine, BANNED_EXPRESSIONS
from src.style_analyzer import StyleAnalyzer
from src.scheduler import PostScheduler, PEAK_SLOTS


class TestContentValidation:
    """コンテンツバリデーションのテスト"""

    def _make_engine(self):
        """テスト用エンジン（API呼出なし）"""
        # validate_tweet メソッドのみテスト
        engine = ContentEngine.__new__(ContentEngine)
        engine.style_prompt = ""
        return engine

    def test_valid_tweet(self):
        """正常なツイートのバリデーション"""
        engine = self._make_engine()
        valid, issue = engine.validate_tweet(
            "お金持ちと貧乏人の差は、能力じゃない。思考の差だ。"
        )
        assert valid is True
        assert issue == ""

    def test_over_140_chars(self):
        """140文字超過の検出"""
        engine = self._make_engine()
        long_text = "あ" * 141
        valid, issue = engine.validate_tweet(long_text)
        assert valid is False
        assert "文字数超過" in issue

    def test_exactly_140_chars(self):
        """140文字ちょうどは許可"""
        engine = self._make_engine()
        exact_text = "あ" * 140
        valid, issue = engine.validate_tweet(exact_text)
        assert valid is True

    def test_too_short(self):
        """10文字未満の検出"""
        engine = self._make_engine()
        valid, issue = engine.validate_tweet("短い")
        assert valid is False
        assert "文字数不足" in issue

    def test_hashtag_rejected(self):
        """ハッシュタグの検出"""
        engine = self._make_engine()
        valid, issue = engine.validate_tweet(
            "これはテストの投稿です #テスト この投稿にはハッシュタグがあります"
        )
        assert valid is False
        assert "ハッシュタグ" in issue

    def test_fullwidth_hashtag_rejected(self):
        """全角ハッシュタグの検出"""
        engine = self._make_engine()
        valid, issue = engine.validate_tweet(
            "これはテストの投稿です ＃テスト この投稿は全角ハッシュタグがあります"
        )
        assert valid is False
        assert "ハッシュタグ" in issue

    def test_banned_expressions(self):
        """禁止表現の検出"""
        engine = self._make_engine()
        for expr in ["買い", "売り", "必ず儲かる", "おすすめ銘柄"]:
            text = f"この銘柄は{expr}だと思います。これはテスト用の長いテキストです。"
            valid, issue = engine.validate_tweet(text)
            assert valid is False, f"禁止表現「{expr}」が検出されませんでした"

    def test_url_rejected(self):
        """URLの検出"""
        engine = self._make_engine()
        valid, issue = engine.validate_tweet(
            "詳しくはこちら https://example.com をご覧ください投稿テスト"
        )
        assert valid is False
        assert "URL" in issue

    def test_mention_rejected(self):
        """メンションの検出"""
        engine = self._make_engine()
        valid, issue = engine.validate_tweet(
            "@someone に教えてもらった考え方が素晴らしいので共有します"
        )
        assert valid is False
        assert "メンション" in issue


class TestStyleAnalyzer:
    """スタイル分析のテスト"""

    def test_analyze_empty(self):
        """空のツイートリスト"""
        analyzer = StyleAnalyzer()
        profile = analyzer.analyze_tweets([])
        assert profile["total_tweets_analyzed"] == 0
        assert "note" in profile

    def test_analyze_basic(self):
        """基本的なスタイル分析"""
        analyzer = StyleAnalyzer()
        tweets = [
            {"text": "富裕層は時間の使い方が違う。お金は取り戻せるが、時間は取り戻せないのだ。"},
            {"text": "成功者の共通点は朝の習慣にある。最も大切な仕事を、誰にも邪魔されない朝にやるのだ。"},
            {"text": "自己投資こそ最高のリターンをもたらす。スキルは誰にも奪えない資産である。"},
        ]
        profile = analyzer.analyze_tweets(tweets)
        assert profile["total_tweets_analyzed"] == 3
        assert profile["avg_length"] > 0
        assert "char_ratios" in profile

    def test_char_ratios(self):
        """文字比率の計算"""
        analyzer = StyleAnalyzer()
        tweets = [{"text": "漢字とひらがなのテスト"}]
        profile = analyzer.analyze_tweets(tweets)
        ratios = profile["char_ratios"]
        total = ratios["kanji_pct"] + ratios["hiragana_pct"] + ratios["katakana_pct"] + ratios["other_pct"]
        assert abs(total - 100.0) < 1.0  # 四捨五入誤差を許容

    def test_style_prompt_fragment(self):
        """プロンプト用テキスト生成"""
        analyzer = StyleAnalyzer()
        fragment = analyzer.get_style_prompt_fragment()
        assert "文体ルール" in fragment
        assert "語尾パターン" in fragment


class TestScheduler:
    """スケジューラーのテスト"""

    def test_peak_slots_count(self):
        """ピークタイムスロットが10件あること"""
        assert len(PEAK_SLOTS) == 10

    def test_period_distribution(self):
        """朝3件・昼3件・夜4件の分布"""
        morning = sum(1 for s in PEAK_SLOTS if s["period"] == "morning")
        noon = sum(1 for s in PEAK_SLOTS if s["period"] == "noon")
        evening = sum(1 for s in PEAK_SLOTS if s["period"] == "evening")
        assert morning == 3
        assert noon == 3
        assert evening == 4

    def test_assign_time_slots(self):
        """タイムスロット割り当て"""
        scheduler = PostScheduler()
        tweets = [
            {"text": f"テスト投稿{i}", "status": "pending"} for i in range(5)
        ]
        assigned = scheduler.assign_time_slots(tweets)
        assert all("scheduled_time" in t for t in assigned)
        assert all("period" in t for t in assigned)


class TestCleanOutput:
    """出力クリーニングのテスト"""

    def _make_engine(self):
        engine = ContentEngine.__new__(ContentEngine)
        engine.style_prompt = ""
        return engine

    def test_remove_quotes(self):
        """引用符の除去"""
        engine = self._make_engine()
        assert engine._clean_output('"テスト投稿"') == "テスト投稿"
        assert engine._clean_output("「テスト投稿」") == "テスト投稿"

    def test_remove_numbering(self):
        """先頭番号の除去"""
        engine = self._make_engine()
        assert engine._clean_output("1. テスト投稿") == "テスト投稿"
        assert engine._clean_output("2) テスト投稿") == "テスト投稿"

    def test_multiline_takes_first(self):
        """複数行の場合は最初の行のみ"""
        engine = self._make_engine()
        result = engine._clean_output("一行目\n二行目\n三行目")
        assert result == "一行目"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
