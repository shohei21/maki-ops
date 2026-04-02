"""
Team C: 投稿チーム
生成した投稿文をX（Twitter）に自動投稿し、ログを記録する
"""
import csv
import json
from datetime import datetime, date
from pathlib import Path

import tweepy

from shared.logger import get_logger

logger = get_logger("posting")

POSTED_LOG = Path(__file__).parent.parent.parent / "content" / "posted" / "posted_log.csv"
LOG_HEADERS = ["date", "time", "type", "text", "tweet_id", "url"]


def _init_log():
    POSTED_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not POSTED_LOG.exists():
        with open(POSTED_LOG, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow(LOG_HEADERS)


class XPoster:
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        access_token: str,
        access_token_secret: str,
    ):
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        _init_log()

    def post(self, text: str, post_type: str = "daily", dry_run: bool = False) -> dict:
        """1件投稿してログに記録。dry_run=Trueなら実際には投稿しない"""
        now = datetime.now()
        if dry_run:
            logger.info(f"[DRY-RUN] 投稿スキップ: {text[:50]}...")
            return {"tweet_id": "dry_run", "url": "", "text": text}

        try:
            resp = self.client.create_tweet(text=text)
            tweet_id = resp.data["id"]
            url = f"https://x.com/i/web/status/{tweet_id}"
            logger.info(f"投稿完了: {url}")
            self._log(now, post_type, text, tweet_id, url)
            return {"tweet_id": tweet_id, "url": url, "text": text}
        except tweepy.TweepyException as e:
            logger.error(f"投稿失敗: {e}")
            return {"error": str(e), "text": text}

    def post_scheduled(self, posts: list[dict], dry_run: bool = False) -> list[dict]:
        """投稿リストを順番に投稿（間隔なし・呼び出し元でスケジューリング）"""
        results = []
        for p in posts:
            result = self.post(p.get("text", ""), p.get("type", "daily"), dry_run=dry_run)
            results.append(result)
        return results

    def _log(self, dt: datetime, post_type: str, text: str, tweet_id: str, url: str):
        with open(POSTED_LOG, "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([
                dt.strftime("%Y-%m-%d"),
                dt.strftime("%H:%M:%S"),
                post_type,
                text.replace("\n", " "),
                tweet_id,
                url,
            ])

    def get_recent_posts(self, days: int = 7) -> list[dict]:
        """直近N日の投稿ログを返す"""
        if not POSTED_LOG.exists():
            return []
        results = []
        with open(POSTED_LOG, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                results.append(row)
        return results[-days * 3:]  # 1日3投稿想定
