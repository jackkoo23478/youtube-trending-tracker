# YouTube Trending Tracker

Every Monday, a GitHub Actions job fetches the top 5 most popular YouTube videos in
India, the US, Indonesia, Brazil and Hong Kong, tags each with a type (AI, comedy, music, gaming…),
and saves them to a Notion database.

## Setup

1. **YouTube API key**: Google Cloud Console → enable *YouTube Data API v3* → create an API key.
2. **Notion token**: notion.so/my-integrations → new integration → copy the secret (`ntn_...`).
   Then open the Notion database → `⋯` → *Connections* → add the integration.
3. In this repo: *Settings → Secrets and variables → Actions → New repository secret*:
   - `YT_API_KEY`
   - `NOTION_TOKEN`
4. Test it: *Actions* tab → *Weekly YouTube top videos* → *Run workflow*.

## Notes

- Uses `videos.list?chart=mostPopular`. Since YouTube removed its Trending page (July 2025),
  this chart mostly reflects trending music, movies and gaming.
- "AI" is detected by keywords in the title/tags; other types come from YouTube's category.
- Both APIs are free; one run uses about 5 of the 10,000 daily YouTube quota units.

## Run locally

```bash
pip install -r requirements.txt
export YT_API_KEY=...
export NOTION_TOKEN=...
python fetch_youtube_popular.py
```
