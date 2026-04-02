#!/usr/bin/env python3
"""
X (Twitter) バズ記事収集スクリプト
SocialData API を使って、いいね数・期間指定でバズ記事を収集する

使い方:
    export SOCIALDATA_API_KEY=your_key
    python scripts/collect_x_articles.py --min-faves 1000 --since 2026-03-01 --until 2026-03-25
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# ── パス設定 ────────────────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent.parent
CACHE_DIR   = ROOT_DIR / "research" / ".cache"
OUTPUT_DIR  = ROOT_DIR / "research" / "trends"
API_BASE    = "https://api.socialdata.tools"


# ── API ─────────────────────────────────────────────────────────────────────

def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def search_tweets(query: str, api_key: str, max_pages: int = 10) -> list[dict]:
    """SocialData 検索API。ページネーションで全件取得。"""
    all_tweets: list[dict] = []
    next_cursor = None

    for page in range(1, max_pages + 1):
        params: dict = {"query": query, "type": "Latest"}
        if next_cursor:
            params["cursor"] = next_cursor

        resp = requests.get(f"{API_BASE}/twitter/search", headers=_headers(api_key), params=params)
        if resp.status_code >= 500:
            print(f"  ページ {page}: サーバーエラー ({resp.status_code})、ここで打ち切り")
            break
        resp.raise_for_status()
        data = resp.json()

        tweets = data.get("tweets", [])
        all_tweets.extend(tweets)
        print(f"  ページ {page}: {len(tweets)}件 (累計 {len(all_tweets)}件)")

        next_cursor = data.get("next_cursor")
        if not next_cursor or not tweets:
            break

        time.sleep(0.5)  # レートリミット対策

    return all_tweets


def get_article_detail(tweet_id: str, api_key: str) -> dict | None:
    """記事詳細取得。キャッシュがあればAPIコールをスキップ。"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = CACHE_DIR / f"{tweet_id}.json"

    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    resp = requests.get(f"{API_BASE}/twitter/article/{tweet_id}", headers=_headers(api_key))
    if resp.status_code in (404, 402):
        return None
    resp.raise_for_status()

    data = resp.json()
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    time.sleep(0.3)
    return data


# ── 変換・判定 ───────────────────────────────────────────────────────────────

def is_japanese_profile(tweet: dict) -> bool:
    """プロフィール情報から日本語アカウントか判定（APIコスト0）。"""
    user = tweet.get("user", {})
    if user.get("lang") == "ja":
        return True
    text = " ".join(filter(None, [
        user.get("description", ""),
        user.get("name", ""),
        user.get("location", ""),
    ]))
    return any('\u3040' <= c <= '\u9fff' for c in text)


def draftjs_to_markdown(article: dict) -> str:
    """Draft.js ブロック構造を Markdown テキストに変換。
    APIレスポンス構造: response["article"]["content_state"]["blocks"]
    """
    if not article:
        return ""

    # /twitter/article/{id} のレスポンス構造に対応
    inner = article.get("article", article)
    content = inner.get("content_state", inner.get("content", {}))

    # 文字列がそのまま入っている場合
    if isinstance(content, str):
        return content

    blocks = content.get("blocks", [])
    if not blocks:
        title = inner.get("title", "")
        body  = inner.get("body", "")
        return f"# {title}\n\n{body}".strip() if title else body

    TYPE_MAP = {
        "header-one":           "# {}",
        "header-two":           "## {}",
        "header-three":         "### {}",
        "blockquote":           "> {}",
        "unordered-list-item":  "- {}",
        "ordered-list-item":    "1. {}",
        "code-block":           "```\n{}\n```",
    }
    lines = []
    for block in blocks:
        text = block.get("text", "")
        fmt  = TYPE_MAP.get(block.get("type", "unstyled"), "{}")
        lines.append(fmt.format(text))

    return "\n\n".join(lines)


# ── 加工 ─────────────────────────────────────────────────────────────────────

def deduplicate(articles: list[dict]) -> list[dict]:
    """タイトル+著者でユニーク化し、いいね最大のものを残す。"""
    seen: dict[tuple, dict] = {}
    for a in articles:
        key = (a.get("title", ""), a.get("author", ""))
        if key not in seen or seen[key]["favorite_count"] < a["favorite_count"]:
            seen[key] = a
    return list(seen.values())


# ── レポート出力 ──────────────────────────────────────────────────────────────

def generate_report(
    articles: list[dict],
    output_path: Path,
    min_faves: int,
    since: str,
    until: str,
) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# X バズ記事収集レポート",
        "",
        f"- 収集日時: {now}",
        f"- いいね数: {min_faves:,} 以上",
        f"- 期間: {since} 〜 {until}",
        f"- 件数: {len(articles)} 件",
        "",
        "---",
        "",
    ]

    for i, a in enumerate(articles, 1):
        title   = a.get("title") or a.get("text", "")[:60]
        author  = a.get("author", "")
        screen  = a.get("author_screen_name", "")
        faves   = a.get("favorite_count", 0)
        rts     = a.get("retweet_count", 0)
        url     = a.get("url", "")
        lang    = "ja" if a.get("is_japanese") else "other"
        preview = a.get("markdown_content", "")[:300]
        suffix  = "…" if len(a.get("markdown_content", "")) > 300 else ""

        lines += [
            f"## {i}. {title}",
            "",
            f"| 項目 | 値 |",
            f"|---|---|",
            f"| 著者 | {author} (@{screen}) |",
            f"| 言語 | {lang} |",
            f"| いいね | {faves:,} |",
            f"| RT | {rts:,} |",
            f"| URL | {url} |",
            "",
        ]
        if preview:
            lines += [preview + suffix, ""]
        lines += ["---", ""]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nレポート出力: {output_path}")


# ── メイン ────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="X バズ記事収集ツール (SocialData API)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--min-faves",  type=int, default=1000,  help="最小いいね数")
    parser.add_argument("--since",      required=True,           help="開始日 YYYY-MM-DD")
    parser.add_argument("--until",      required=True,           help="終了日 YYYY-MM-DD")
    parser.add_argument("--lang",       choices=["ja", "other", "all"], default="all",
                        help="言語フィルター")
    parser.add_argument("--max-pages",  type=int, default=50,    help="最大ページ数")
    parser.add_argument("--no-detail",  action="store_true",
                        help="記事詳細取得をスキップ（コスト削減）")
    parser.add_argument("--keyword",    default="",
                        help="追加キーワード/ハッシュタグ（例: '#裏垢女子 OR #裏垢'）。指定するとurl:x.com/i/articleフィルターを外す")
    parser.add_argument("--output",     help="出力ファイル名（省略時は自動生成）")
    args = parser.parse_args()

    api_key = os.environ.get("SOCIALDATA_API_KEY")
    if not api_key:
        sys.exit("ERROR: 環境変数 SOCIALDATA_API_KEY が設定されていません")

    # ① クエリ構築
    if args.keyword:
        # キーワード指定時は通常ツイートを対象（url:x.com/i/article を外す）
        query = (
            f"({args.keyword}) "
            f"min_faves:{args.min_faves} "
            f"-filter:replies "
            f"since:{args.since} "
            f"until:{args.until}"
        )
    else:
        query = (
            f"url:x.com/i/article "
            f"min_faves:{args.min_faves} "
            f"-filter:replies "
            f"since:{args.since} "
            f"until:{args.until}"
        )
    print(f"検索クエリ: {query}\n")

    # ② 検索
    print("[ STEP 1 ] ツイート検索中...")
    tweets = search_tweets(query, api_key, max_pages=args.max_pages)
    print(f"→ 合計 {len(tweets)} 件\n")

    # ③ 言語判定 & 一次分類
    print("[ STEP 2 ] 言語判定...")
    results: list[dict] = []
    for tweet in tweets:
        is_ja = is_japanese_profile(tweet)
        if args.lang == "ja"    and not is_ja: continue
        if args.lang == "other" and is_ja:     continue

        results.append({
            "id_str":              tweet.get("id_str", ""),
            "text":                tweet.get("full_text", tweet.get("text", "")),
            "favorite_count":      tweet.get("favorite_count", 0),
            "retweet_count":       tweet.get("retweet_count", 0),
            "author":              tweet.get("user", {}).get("name", ""),
            "author_screen_name":  tweet.get("user", {}).get("screen_name", ""),
            "url":                 (
                f"https://x.com/"
                f"{tweet.get('user', {}).get('screen_name', '')}/"
                f"status/{tweet.get('id_str', '')}"
            ),
            "is_japanese":         is_ja,
            "title":               "",
            "markdown_content":    tweet.get("full_text", tweet.get("text", "")),
        })
    print(f"→ 言語フィルター後: {len(results)} 件\n")

    # ④ 記事詳細取得
    if not args.no_detail:
        print("[ STEP 3 ] 記事詳細取得中（キャッシュ利用）...")
        for i, article in enumerate(results, 1):
            detail = get_article_detail(article["id_str"], api_key)
            if detail:
                article["title"]            = detail.get("article", {}).get("title", "")
                article["markdown_content"] = draftjs_to_markdown(detail)
            if i % 10 == 0 or i == len(results):
                print(f"  {i}/{len(results)} 件処理済み")
        print()

    # ⑤ 重複除去
    before = len(results)
    results = deduplicate(results)
    print(f"[ STEP 4 ] 重複除去: {before} → {len(results)} 件\n")

    # ⑥ エンゲージメント降順ソート
    results.sort(key=lambda x: x["favorite_count"], reverse=True)

    # ⑧ レポート出力
    fname = args.output or f"buzz_{args.since}_{args.until}_faves{args.min_faves}.md"
    generate_report(results, OUTPUT_DIR / fname, args.min_faves, args.since, args.until)

    # JSON サイドカー出力（Sheets連携用）
    json_path = (OUTPUT_DIR / fname).with_suffix(".json")
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON出力: {json_path}")

    print(f"完了! {len(results)} 件のバズ記事を収集しました。")


if __name__ == "__main__":
    main()
