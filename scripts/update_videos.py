#!/usr/bin/env python3
"""
YouTube RSSから登録チャンネルの新着動画を取得し、
data/videos.jsonを更新します。

OPENAI_API_KEYが設定されている場合は、タイトルと概要欄を基に
日本語要約・優先度・タグを生成します。未設定でも動作します。
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
CHANNELS_PATH = ROOT / "channels.json"
OUTPUT_PATH = ROOT / "data" / "videos.json"
MAX_VIDEOS_PER_CHANNEL = int(os.getenv("MAX_VIDEOS_PER_CHANNEL", "8"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-mini")
RSS_TEMPLATE = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def fallback_summary(title: str, description: str) -> dict[str, Any]:
    source = clean_text(description)
    if source:
        summary = source[:240] + ("…" if len(source) > 240 else "")
    else:
        summary = f"「{title}」に関する新着動画です。動画の概要欄が短いため、詳細はリンク先で確認してください。"

    lowered = f"{title} {description}".lower()
    high_words = ("ai", "生成ai", "claude", "chatgpt", "資産", "金利", "為替", "日本経済")
    priority = "high" if any(word in lowered for word in high_words) else "medium"

    tags = []
    keyword_map = {
        "AI": ("ai", "chatgpt", "claude", "生成ai", "エージェント"),
        "資産管理": ("資産", "投資", "金", "株", "富裕層"),
        "国際情勢": ("ニュージーランド", "中国", "移民", "海外", "戦争"),
        "日本経済": ("日本", "金利", "為替", "財政", "産業"),
    }
    for label, words in keyword_map.items():
        if any(word in lowered for word in words):
            tags.append(label)

    return {
        "summary": summary,
        "priority": priority,
        "tags": tags[:4] or ["新着動画"],
    }


def call_openai(title: str, description: str, category: str) -> dict[str, Any]:
    if not OPENAI_API_KEY:
        return fallback_summary(title, description)

    prompt = f"""
次のYouTube動画について、ダッシュボード表示用の情報を日本語で作成してください。
動画そのものを視聴したとは表現せず、タイトルと概要欄から判断した内容であることを守ってください。

利用者の関心:
自治体BPR、生成AI、国際情勢、資産管理、投資、仕事と暮らしの自動化

チャンネル分類:
{category}

タイトル:
{title}

概要欄:
{clean_text(description)}

JSONだけを返してください。
形式:
{{
  "summary": "140～240文字の要約",
  "priority": "high または medium または low",
  "tags": ["最大4個"]
}}
""".strip()

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "input": prompt,
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()

    text = payload.get("output_text")
    if not text:
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text")
                    break
            if text:
                break

    if not text:
        raise ValueError("OpenAI APIから出力テキストを取得できませんでした。")

    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
    data = json.loads(text)

    if data.get("priority") not in {"high", "medium", "low"}:
        data["priority"] = "medium"

    if not isinstance(data.get("tags"), list):
        data["tags"] = []

    return {
        "summary": str(data.get("summary", "")).strip(),
        "priority": data["priority"],
        "tags": [str(x) for x in data["tags"][:4]],
    }


def get_thumbnail(entry: Any, video_id: str) -> str:
    media_group = entry.get("media_group") or []
    if media_group:
        thumbnails = media_group[0].get("media_thumbnail") or []
        if thumbnails and thumbnails[0].get("url"):
            return thumbnails[0]["url"]
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def update() -> None:
    channels = json.loads(CHANNELS_PATH.read_text(encoding="utf-8"))
    videos: list[dict[str, Any]] = []
    errors: list[str] = []

    for channel in channels:
        channel_id = channel["channelId"]
        feed_url = RSS_TEMPLATE.format(channel_id=channel_id)
        feed = feedparser.parse(feed_url)

        if getattr(feed, "bozo", False) and not feed.entries:
            errors.append(f'{channel["name"]}: RSS取得失敗')
            continue

        for entry in feed.entries[:MAX_VIDEOS_PER_CHANNEL]:
            video_id = entry.get("yt_videoid") or entry.get("videoid")
            if not video_id:
                match = re.search(r"(?:v=|/)([\w-]{11})(?:[?&/]|$)", entry.get("link", ""))
                video_id = match.group(1) if match else None
            if not video_id:
                continue

            title = clean_text(entry.get("title"))
            description = ""
            media_group = entry.get("media_group") or []
            if media_group:
                description = media_group[0].get("media_description", "")
            description = description or entry.get("summary", "")

            try:
                ai = call_openai(title, description, channel.get("category", ""))
            except Exception as exc:
                print(f"要約生成をスキップ: {title}: {exc}", file=sys.stderr)
                ai = fallback_summary(title, description)

            videos.append({
                "videoId": video_id,
                "channel": channel["name"],
                "channelHandle": channel.get("handle", ""),
                "title": title,
                "published": entry.get("published") or entry.get("updated"),
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail": get_thumbnail(entry, video_id),
                "description": clean_text(description),
                "summary": ai["summary"],
                "priority": ai["priority"],
                "tags": ai["tags"],
                "durationMinutes": None,
            })

    videos.sort(key=lambda item: item.get("published") or "", reverse=True)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(
            {
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "channelCount": len(channels),
                "videos": videos,
                "errors": errors,
                "message": "本日の新着なし" if not videos and not errors else "",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"{len(videos)}件を {OUTPUT_PATH} に保存しました。")
    if errors:
        print("エラー: " + " / ".join(errors), file=sys.stderr)


if __name__ == "__main__":
    update()
