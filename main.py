"""
X自動運用システム - メインエントリポイント
対話型モード付き統合ワークフロー
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("x_auto.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def setup_api_client():
    """X APIクライアントのセットアップ"""
    from src.api_handler import XAPIClient

    try:
        client = XAPIClient()
        logger.info("X APIクライアント初期化成功")
        return client
    except ValueError as e:
        logger.error(f"APIクライアント初期化失敗: {e}")
        return None


def run_style_analysis(api_client, auto=False):
    """過去ツイートのスタイル分析を実行"""
    from src.style_analyzer import StyleAnalyzer

    analyzer = StyleAnalyzer()

    # 保存済みプロファイルがあれば読み込み
    profile = analyzer.load_profile()
    if profile:
        logger.info("保存済みスタイルプロファイルを読み込みました。")
        print("\n📝 保存済みスタイルプロファイルあり")
        
        if auto:
            use_cached = "n"  # 自動モード時は再分析しない（基本キャッシュ利用）
        else:
            use_cached = input("再分析しますか？ (y/N): ").strip().lower()
            
        if use_cached != "y":
            return analyzer.get_style_prompt_fragment(profile)

    if not api_client:
        logger.warning("APIクライアントなし。デフォルトプロファイルを使用。")
        return analyzer.get_style_prompt_fragment()

    print("\n🔍 過去ツイートを取得してスタイル分析中...")
    tweets = api_client.get_user_tweets(max_results=50)
    if not tweets:
        logger.warning("過去ツイートが取得できませんでした。デフォルトプロファイルを使用。")
        return analyzer.get_style_prompt_fragment()

    profile = analyzer.analyze_tweets(tweets)
    analyzer.save_profile(profile)

    print(f"  分析完了: {profile['total_tweets_analyzed']} 件")
    print(f"  平均文字数: {profile['avg_length']}")
    print(f"  主要語尾: {', '.join([e[0] for e in profile['endings'][:3]])}")

    # 過去ツイートをキャッシュに保存
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(data_dir, exist_ok=True)
    with open(os.path.join(data_dir, "past_tweets.json"), "w", encoding="utf-8") as f:
        json.dump(tweets, f, ensure_ascii=False, indent=2)

    return analyzer.get_style_prompt_fragment(profile)


def run_research(api_client, auto=False):
    """バズ投稿リサーチを実行"""
    from src.research import ResearchModule

    researcher = ResearchModule(api_client)

    # 保存済みリサーチ結果があるか確認
    existing = researcher.load_research_results()
    if existing:
        print(f"\n📚 保存済みリサーチ結果: {len(existing)} 件")
        
        if auto:
            refresh = "y"  # 自動モード時は常にリフレッシュ（最新情報を取得）
        else:
            refresh = input("再リサーチしますか？ (y/N): ").strip().lower()
            
        if refresh != "y":
            return existing

    print("\n🔍 バズ投稿をリサーチ中...")
    try:
        results = researcher.research_all_genres()
        if results:
            researcher.save_research_results(results)
            print(f"  リサーチ完了: {len(results)} 件のバズ投稿を取得")

            # パターン分析
            analysis = researcher.analyze_buzz_patterns(results)
            print(f"  平均文字数: {analysis['avg_length']}")
            if analysis["patterns"]:
                print(f"  主要パターン: {', '.join([p[0] for p in analysis['patterns'][:3]])}")
            return results
        else:
            logger.warning("API検索結果なし。サンプルデータを使用。")
    except Exception as e:
        logger.warning(f"APIリサーチ失敗: {e}")

    # フォールバック: サンプルデータ
    print("  📝 サンプルバズ投稿を使用")
    sample = researcher.get_sample_buzz_tweets()
    return sample


def generate_tweets(style_prompt, reference_tweets, count=10):
    """ツイート生成"""
    from src.content_engine import ContentEngine

    # ユーザーのアイデアを読み込む
    user_thoughts = None
    ideas_path = os.path.join(os.path.dirname(__file__), "data", "ideas.txt")
    if os.path.exists(ideas_path):
        try:
            with open(ideas_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                # コメント行を除去して有効なテキストのみ抽出
                lines = [l for l in content.split("\n") if not l.strip().startswith("#")]
                cleaned_thoughts = "\n".join(lines).strip()
                if cleaned_thoughts:
                    user_thoughts = cleaned_thoughts
                    print(f"\n💡 ユーザーの思考メモを読み込みました:\n{'-'*40}\n{user_thoughts[:100]}...\n{'-'*40}")
        except Exception as e:
            logger.warning(f"アイデアファイルの読み込み失敗: {e}")

    engine = ContentEngine(style_prompt=style_prompt)

    ref_texts = [t["text"] for t in reference_tweets[:5]] if reference_tweets else None

    print(f"\n✍️  ツイートを {count} 件生成中...")
    tweets = engine.generate_batch(
        count=count,
        reference_tweets=ref_texts,
        user_thoughts=user_thoughts
    )
    print(f"  生成完了: {len(tweets)} 件")
    return tweets


def interactive_review(tweets: list[str]) -> list[str]:
    """
    対話型モードでツイートを確認・修正する。

    Returns:
        承認されたツイートのリスト
    """
    approved = []
    print("\n" + "=" * 60)
    print("📋 投稿レビューモード（対話型）")
    print("  [a] 承認  [s] スキップ  [e] 編集  [q] 終了")
    print("=" * 60)

    for i, tweet in enumerate(tweets, 1):
        print(f"\n--- [{i}/{len(tweets)}] ({len(tweet)}文字) ---")
        print(f"  {tweet}")
        print()

        while True:
            action = input("  操作 [a/s/e/q]: ").strip().lower()
            if action == "a":
                approved.append(tweet)
                print("  ✅ 承認")
                break
            elif action == "s":
                print("  ⏭️  スキップ")
                break
            elif action == "e":
                new_text = input("  修正テキスト: ").strip()
                if new_text:
                    if len(new_text) > 140:
                        print(f"  ⚠️  140文字を超えています ({len(new_text)}文字)")
                        continue
                    approved.append(new_text)
                    print(f"  ✅ 修正して承認 ({len(new_text)}文字)")
                else:
                    print("  空のテキストはスキップされます")
                break
            elif action == "q":
                print("  🛑 レビュー終了")
                return approved
            else:
                print("  無効な操作です。a/s/e/q を入力してください。")

    print(f"\n✅ 承認済み: {len(approved)} 件 / {len(tweets)} 件")
    return approved


def schedule_tweets(approved_tweets: list[str], api_client):
    """承認済みツイートをスケジュールに追加"""
    from src.scheduler import PostScheduler

    scheduler = PostScheduler(api_client=api_client)
    scheduler.stock_tweets(approved_tweets)

    # タイムスロットを割り当て（最大10件まで）
    pending = scheduler.get_pending_tweets(count=10)
    assigned = scheduler.assign_time_slots(pending)

    # 更新を保存
    all_scheduled = scheduler._load_scheduled()
    for item in all_scheduled:
        for assigned_item in assigned:
            if item["text"] == assigned_item["text"] and item["status"] == "pending":
                item["scheduled_time"] = assigned_item.get("scheduled_time")
                item["period"] = assigned_item.get("period")
                break
    scheduler._save_scheduled(all_scheduled)

    print(scheduler.get_schedule_summary())
    return scheduler


def main():
    parser = argparse.ArgumentParser(
        description="X自動運用システム - バズ投稿リサーチ・生成・予約投稿",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python main.py --generate            投稿案を生成してストック
  python main.py --generate --auto     自動承認モードで生成
  python main.py --run                 予約投稿を実行（デーモン）
  python main.py --generate --dry-run  ドライラン（API呼出なし）
  python main.py --status              スケジュール状況を確認
        """,
    )
    parser.add_argument(
        "--generate", action="store_true", help="投稿案を生成してストック"
    )
    parser.add_argument(
        "--run", action="store_true", help="予約投稿を実行（デーモンモード）"
    )
    parser.add_argument(
        "--auto", action="store_true", help="人間承認をスキップ（自動モード）"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="ドライラン（API投稿なし）"
    )
    parser.add_argument(
        "--count", type=int, default=10, help="生成件数（デフォルト: 10）"
    )
    parser.add_argument(
        "--status", action="store_true", help="スケジュール状況を確認"
    )
    parser.add_argument(
        "--clear", action="store_true", help="投稿済みアイテムをクリア"
    )
    parser.add_argument(
        "--post-now", action="store_true", help="生成後すぐに投稿する（GitHub Actions用）"
    )
    parser.add_argument(
        "--execute-scheduled", action="store_true", help="時間が来た予約投稿を1回のみ実行（GitHub Actions用）"
    )
    parser.add_argument(
        "--cron", action="store_true", help="時間が来た投稿を確認して実行（--execute-scheduled のエイリアス）"
    )
    parser.add_argument(
        "--reply", action="store_true", help="メンションをチェックして自動返信を実行"
    )
    parser.add_argument(
        "--engage", action="store_true", help="エゴサ（キーワード検索）していいねを実行"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("🚀 X自動運用システム")
    print(f"   アカウント: @{os.getenv('X_USERNAME', '3m6LGY8PTkQKx63')}")
    print(f"   日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ステータス確認
    if args.status:
        from src.scheduler import PostScheduler

        scheduler = PostScheduler()
        print(scheduler.get_schedule_summary())
        return

    # クリア
    if args.clear:
        from src.scheduler import PostScheduler

        scheduler = PostScheduler()
        scheduler.clear_completed()
        print("✅ 投稿済みアイテムをクリアしました")
        return

    # APIクライアントセットアップ
    api_client = None
    if not args.dry_run:
        api_client = setup_api_client()
        if not api_client:
            print("\n⚠️  APIキーが未設定です。ドライランモードで続行します。")
            args.dry_run = True

    # 単発実行モード（GitHub Actions用）
    if args.execute_scheduled or args.cron or args.reply or args.engage:
        from src.scheduler import PostScheduler
        from src.reply_handler import ReplyHandler
        from src.content_engine import ContentEngine
        from src.engagement_handler import EngagementHandler

        # スケジュール投稿のチェック
        if args.execute_scheduled or args.cron:
            scheduler = PostScheduler(api_client=api_client)
            print("\n⏳ 予約投稿をチェック中...")
            results = scheduler.execute_scheduled(dry_run=args.dry_run)
            if results:
                print(f"✅ {len(results)} 件の投稿を実行しました")
            else:
                print("📭 現在、実行待ちの予約投稿はありません")

        # 自動リプライのチェック（明示的に --reply が指定された場合のみ）
        if args.reply:
            engine = ContentEngine()
            replier = ReplyHandler(api_client=api_client, content_engine=engine)
            print("\n📩 メンションをチェック中...")
            replier.run(dry_run=args.dry_run)
            print("✅ メンションチェック完了")
        
        # エゴサ・いいねのチェック
        if args.engage or args.cron:
            engager = EngagementHandler(api_client=api_client)
            print("\n🔍 エゴサ・いいねを実行中...")
            engager.run_ego_search_and_like(dry_run=args.dry_run)
            print("✅ エゴサ・いいね完了")
        
        return

    # デーモンモード
    if args.run:
        from src.scheduler import PostScheduler

        scheduler = PostScheduler(api_client=api_client)
        print("\n📡 デーモンモード起動")
        print("   Ctrl+C で停止")
        scheduler.run_daemon(dry_run=args.dry_run)
        return

    # 生成モード
    if args.generate:
        # Step 1: スタイル分析
        style_prompt = run_style_analysis(api_client, auto=args.auto)

        # Step 2: バズ投稿リサーチ
        reference_tweets = run_research(api_client, auto=args.auto)

        # Step 3: ツイート生成
        tweets = generate_tweets(style_prompt, reference_tweets, count=args.count)

        if not tweets:
            print("\n❌ ツイートの生成に失敗しました。")
            return

        # Step 4: レビュー
        if args.auto:
            print("\n🤖 自動承認モード: 全てのツイートを承認")
            approved = tweets
        else:
            approved = interactive_review(tweets)

        if not approved:
            print("\n⚠️  承認されたツイートがありません。")
            return

        # Step 5: スケジュール or 即投稿
        if args.post_now:
            print("\n🚀 即時投稿モード: 生成されたツイートを直ちに投稿します")
            from src.scheduler import PostScheduler

            scheduler = PostScheduler(api_client=api_client)
            # 一旦ストックに追加（履歴管理のため）
            scheduler.stock_tweets(approved)
            
            # 強制的に時間を現在にして実行
            # 注意: stock_tweetsで追加された最新のpendingアイテムのみを対象とする
            # 簡易実装として、pendingのものをすべて実行対象にする（通常は1件のみのはず）
            all_scheduled = scheduler._load_scheduled()
            for item in all_scheduled:
                if item["status"] == "pending":
                    # 過去の時間に設定して実行対象にする
                    item["scheduled_time"] = (datetime.now() - timedelta(minutes=1)).isoformat()
            
            scheduler._save_scheduled(all_scheduled)
            scheduler.execute_scheduled(dry_run=args.dry_run)
            print("✨ 投稿完了")
            return

        schedule_tweets(approved, api_client if not args.dry_run else None)

        if not args.dry_run:
            run_now = input("\n今すぐ予約投稿を実行しますか？ (y/N): ").strip().lower()
            if run_now == "y":
                from src.scheduler import PostScheduler

                scheduler = PostScheduler(api_client=api_client)
                scheduler.execute_scheduled()
        else:
            print("\n🏃 ドライラン完了（実際の投稿は行われません）")

        return

    # 引数なしの場合はヘルプ表示
    parser.print_help()


if __name__ == "__main__":
    main()
