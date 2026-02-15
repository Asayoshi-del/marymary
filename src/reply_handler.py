import json
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class ReplyHandler:
    """メンションへの自動返信を管理するクラス"""

    def __init__(self, api_client, content_engine):
        self.api = api_client
        self.engine = content_engine
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.state_file = os.path.join(self.data_dir, "reply_state.json")

    def run(self, dry_run: bool = False):
        """メンションをチェックして返信する"""
        state = self._load_state()
        last_id = state.get("last_mention_id")

        logger.info(f"メンションをチェック中... (since_id: {last_id})")
        mentions = self.api.get_mentions(since_id=last_id)

        if not mentions:
            logger.info("新しいメンションはありません")
            return

        # 古い順に処理（ID順）
        for mention in reversed(mentions):
            try:
                self._process_mention(mention, dry_run)
                # 処理に成功したらIDを更新
                state["last_mention_id"] = mention["id"]
                state["last_updated"] = datetime.now().isoformat()
                self._save_state(state)
            except Exception as e:
                logger.error(f"メンション処理失敗 (ID: {mention['id']}): {e}")

    def _process_mention(self, mention: dict, dry_run: bool):
        """個別のメンションに対して返信を生成・投稿する"""
        logger.info(f"返信生成中: @{mention['author_username']} の投稿「{mention['text'][:30]}...」")
        
        reply_text = self.engine.generate_reply(
            mention_text=mention["text"],
            author_username=mention["author_username"]
        )

        if dry_run:
            logger.info(f"[DRY RUN] 返信投稿: {reply_text}")
        else:
            result = self.api.post_tweet(text=reply_text, reply_to_id=mention["id"])
            if result["success"]:
                logger.info(f"返信完了: ID={result['tweet_id']}")
            else:
                raise Exception(result.get("error", "Unknown error"))

    def _load_state(self) -> dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"last_mention_id": None}

    def _save_state(self, state: dict):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
