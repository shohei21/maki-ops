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
LOG_HEADERS = ["no", "date", "time", "type", "text", "tweet_id", "url", "image_path"]


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
        # v2 API（テキスト投稿 + media_id指定）
        self.client = tweepy.Client(
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        # v1.1 API（画像アップロード用）
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        self.api_v1 = tweepy.API(auth)
        _init_log()

    def upload_image(self, image_path: Path) -> str | None:
        """画像をXにアップロードしてmedia_idを返す"""
        try:
            media = self.api_v1.media_upload(filename=str(image_path))
            logger.info(f"画像アップロード完了: media_id={media.media_id_string}")
            return media.media_id_string
        except Exception as e:
            logger.error(f"画像アップロード失敗: {e}")
            return None

    def post(
        self,
        text: str,
        post_type: str = "daily",
        image_path: Path | None = None,
        dry_run: bool = False,
        no: str = "",
    ) -> dict:
        """1件投稿してログに記録。画像があれば添付。dry_run=Trueなら投稿しない"""
        now = datetime.now()
        if dry_run:
            img_info = f" + 画像({image_path.name})" if image_path else ""
            logger.info(f"[DRY-RUN] 投稿スキップ{img_info}: {text[:50]}...")
            return {"tweet_id": "dry_run", "url": "", "text": text}

        # 画像アップロード
        media_ids = None
        if image_path and image_path.exists():
            media_id = self.upload_image(image_path)
            if media_id:
                media_ids = [media_id]

        try:
            resp = self.client.create_tweet(text=text, media_ids=media_ids)
            tweet_id = resp.data["id"]
            url = f"https://x.com/i/web/status/{tweet_id}"
            img_str = str(image_path) if image_path else ""
            logger.info(f"投稿完了: {url}{' (画像付き)' if media_ids else ''}")
            self._log(no, now, post_type, text, tweet_id, url, img_str)
            return {"tweet_id": tweet_id, "url": url, "text": text, "image": img_str}
        except tweepy.TweepyException as e:
            logger.error(f"投稿失敗: {e}")
            return {"error": str(e), "text": text}

    def _log(self, no: str, dt: datetime, post_type: str, text: str, tweet_id: str, url: str, img_path: str = ""):
        with open(POSTED_LOG, "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([
                no,
                dt.strftime("%Y-%m-%d"),
                dt.strftime("%H:%M:%S"),
                post_type,
                text.replace("\n", " "),
                tweet_id,
                url,
                img_path,
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
