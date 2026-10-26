"""
每星期捉印度、美國、印尼、巴西、香港「過去 7 日上載、觀看數最多」嘅 5 條 YouTube 片，存入 Notion。

Setup (一次就得):
  pip install requests
  設定兩個環境變數:
    YT_API_KEY     = 你嘅 YouTube Data API key
    NOTION_TOKEN   = 你嘅 Notion integration secret (ntn_...)

  Windows CMD:  setx YT_API_KEY "xxx"   然後  setx NOTION_TOKEN "xxx"
  (setx 之後要開過新嘅 CMD 先生效)

Run:
  python fetch_youtube_popular.py
"""

import os
import re
from datetime import datetime, timedelta, timezone

import requests

YT_API_KEY = os.environ.get("YT_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
NOTION_DATABASE_ID = "0ed6c81ed2c846199c6d23976ba89e25"   # 「YouTube 每週熱門片」

REGIONS = {"IN": "印度", "US": "美國", "ID": "印尼", "BR": "巴西", "HK": "香港"}
TOP_N = 5
DAYS_BACK = 7        # 只計過去幾多日上載嘅片
CANDIDATES = 15      # search 先攞幾多條候選，再按真實觀看數揀頭 TOP_N 條

# regionCode 只代表「呢個地區睇得到」，唔代表係當地片。
# 加埋語言偏好，結果會比較貼近當地人睇嘅片。
REGION_LANGUAGE = {"IN": "hi", "US": "en", "ID": "id", "BR": "pt", "HK": "zh-Hant"}

# YouTube categoryId -> 你 Notion 入面嘅「類型」
CATEGORY_MAP = {
    "1": "電影/動畫", "30": "電影/動畫", "44": "電影/動畫",
    "10": "音樂",
    "20": "遊戲",
    "23": "搞笑",
    "24": "娛樂",
    "28": "科技",
    "17": "體育",
    "25": "新聞/政治",
    "27": "教育",
    "22": "生活/Vlog", "26": "生活/Vlog", "19": "生活/Vlog", "15": "生活/Vlog",
}

# 片名或 tags 有呢啲字，就當係 AI 片 (YouTube 本身冇 AI 分類)
AI_PATTERN = re.compile(
    r"\bAI\b|\bA\.I\.|chatgpt|openai|\bgpt|gemini|claude|midjourney|\bsora\b|"
    r"artificial intelligence|人工智能|人工智慧|kecerdasan buatan|inteligência artificial",
    re.IGNORECASE,
)


def get_type(snippet: dict) -> str:
    text = snippet.get("title", "") + " " + " ".join(snippet.get("tags", []))
    if AI_PATTERN.search(text):
        return "AI"
    return CATEGORY_MAP.get(snippet.get("categoryId", ""), "其他")


def fetch_top(region: str) -> list[dict]:
    """過去 DAYS_BACK 日上載、喺呢個地區觀看數最多嘅 TOP_N 條片。"""
    since = (datetime.now(timezone.utc) - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1) search.list 揾候選片 (每次 100 quota)
    search = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "id",
            "type": "video",
            "order": "viewCount",
            "publishedAfter": since,
            "regionCode": region,
            "relevanceLanguage": REGION_LANGUAGE.get(region, ""),
            "maxResults": CANDIDATES,
            "key": YT_API_KEY,
        },
        timeout=30,
    )
    search.raise_for_status()
    ids = [it["id"]["videoId"] for it in search.json().get("items", [])]
    if not ids:
        return []

    # 2) videos.list 攞真實觀看數同分類 (1 quota)
    videos = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={"part": "snippet,statistics", "id": ",".join(ids), "key": YT_API_KEY},
        timeout=30,
    )
    videos.raise_for_status()
    items = videos.json().get("items", [])

    # search 嘅排序只係大約，用真實觀看數重新排
    items.sort(key=lambda it: int(it.get("statistics", {}).get("viewCount", 0)), reverse=True)
    return items[:TOP_N]


def to_int(value):
    return int(value) if value not in (None, "") else None


def save_to_notion(item: dict, region_name: str, rank: int, today: str):
    sn, st = item["snippet"], item.get("statistics", {})
    props = {
        "片名": {"title": [{"text": {"content": sn.get("title", "")[:2000]}}]},
        "地區": {"select": {"name": region_name}},
        "排名": {"number": rank},
        "類型": {"select": {"name": get_type(sn)}},
        "頻道": {"rich_text": [{"text": {"content": sn.get("channelTitle", "")}}]},
        "觀看數": {"number": to_int(st.get("viewCount"))},
        "Like 數": {"number": to_int(st.get("likeCount"))},     # 有啲片收埋 like 數
        "留言數": {"number": to_int(st.get("commentCount"))},
        "上載日期": {"date": {"start": sn.get("publishedAt", "")[:10]}},
        "捉取日期": {"date": {"start": today}},
        "Link": {"url": f"https://www.youtube.com/watch?v={item['id']}"},
    }
    resp = requests.post(
        "https://api.notion.com/v1/pages",
        headers={
            "Authorization": f"Bearer {NOTION_TOKEN}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        json={"parent": {"database_id": NOTION_DATABASE_ID}, "properties": props},
        timeout=30,
    )
    if not resp.ok:
        print(f"  Notion error: {resp.status_code} {resp.text[:300]}")
    resp.raise_for_status()


def main():
    if not YT_API_KEY or not NOTION_TOKEN:
        raise SystemExit("請先設定 YT_API_KEY 同 NOTION_TOKEN 環境變數。")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for code, name in REGIONS.items():
        try:
            items = fetch_top(code)
            for rank, item in enumerate(items, start=1):
                save_to_notion(item, name, rank, today)
            print(f"[{name}] 已存 {len(items)} 條片")
        except requests.HTTPError as e:
            print(f"[{name}] 失敗: {e}")


if __name__ == "__main__":
    main()
