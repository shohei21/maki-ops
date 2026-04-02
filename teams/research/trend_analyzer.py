"""
Team D: リサーチチーム
SocialData APIでXのバズ投稿を収集し、まきの投稿に活かせるトレンドを抽出する
"""
import json
import os
import time
from pathlib import Path

import requests

from shared.claude_client import ClaudeClient
from shared.logger import get_logger

logger = get_logger("research")

API_BASE = "https://api.socialdata.tools"

# まきのターゲット層・ジャンルに関連するキーワード
SEARCH_QUERIES = [
    "OL 仕事終わり lang:ja",
    "裏アカ 日常 lang:ja",
    "ひとり飲み 仕事 lang:ja",
    "歳上 好き lang:ja",
    "note 写真 販売 lang:ja",
]


def _fetch_trending(api_key: str, query: str, min_faves: int = 500, max_results: int = 10) -> list[dict]:
    """SocialData APIで検索"""
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    params = {"query": f"{query} min_faves:{min_faves}", "type": "Latest"}
    try:
        resp = requests.get(f"{API_BASE}/twitter/search", headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"API error {resp.status_code}: {query}")
            return []
        tweets = resp.json().get("tweets", [])[:max_results]
        return [
            {
                "query": query,
                "text": t.get("full_text", "")[:200],
                "likes": t.get("favorite_count", 0),
                "retweets": t.get("retweet_count", 0),
                "url": f"https://x.com/i/web/status/{t.get('id_str', '')}",
            }
            for t in tweets
        ]
    except Exception as e:
        logger.warning(f"収集失敗 ({query}): {e}")
        return []


class TrendAnalyzer:
    def __init__(self, claude: ClaudeClient, api_key: str):
        self.claude = claude
        self.api_key = api_key

    def collect_trends(self) -> list[dict]:
        """バズ投稿を収集する"""
        logger.info("Xトレンドを収集中...")
        all_tweets = []
        for query in SEARCH_QUERIES:
            tweets = _fetch_trending(self.api_key, query)
            all_tweets.extend(tweets)
            logger.info(f"  [{query}]: {len(tweets)}件")
            time.sleep(1)
        logger.info(f"合計 {len(all_tweets)} 件収集")
        return all_tweets

    def extract_post_hints(self, tweets: list[dict]) -> str:
        """収集したバズ投稿からまきの投稿に使えるヒントをClaudeで抽出"""
        if not tweets:
            return "今日はトレンドデータなし。定番の日常系投稿で対応。"

        logger.info("トレンドを分析中...")
        sample = tweets[:15]
        tweet_text = "\n".join([f"- ({t['likes']}いいね) {t['text']}" for t in sample])

        return self.claude.complete(
            system="あなたはSNSコンテンツ戦略の専門家です。",
            user=f"""以下のXバズ投稿を分析して、「まき（23歳OL裏アカ）」の今日の投稿に
活かせるヒントを3〜5点、箇条書きで簡潔にまとめてください。

バズ投稿:
{tweet_text}

ヒントは「まきの世界観（日常・感情・グラビア系）」に合うものだけ抽出し、
具体的なキーワードや切り口を提示してください。""",
            max_tokens=800,
        )
