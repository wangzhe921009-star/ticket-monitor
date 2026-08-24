#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
电影票监控 - GitHub Actions 版
执行一次即退出，配合 cron 定时触发（建议每5分钟）
"""

import json
import os
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Optional


# ==================== 配置（从环境变量读取）====================

BARK_URL = os.environ.get("BARK_URL", "")
CINEMA_ID = "37534"
CITY_ID = "10"
MOVIE_ID = "1545360"
CACHE_FILE = "ticket_cache.json"

# 14个监控日期（周五、周六、周日）
MONITOR_DATES = [
    "2026-08-29", "2026-08-30",
    "2026-09-04", "2026-09-05", "2026-09-06",
    "2026-09-11", "2026-09-12", "2026-09-13",
    "2026-09-18", "2026-09-19", "2026-09-20",
    "2026-09-25", "2026-09-26", "2026-09-27",
]


# ==================== 推送模块 ====================

def send_bark(title: str, body: str) -> str:
    if not BARK_URL:
        print("[警告] BARK_URL 未设置，跳过推送")
        return "No BARK_URL"
    try:
        url = f"{BARK_URL}{requests.utils.quote(title)}/{requests.utils.quote(body)}"
        url += "?sound=alarm&group=ticket_monitor"
        resp = requests.get(url, timeout=10)
        return f"Bark: {resp.status_code}"
    except Exception as e:
        return f"Bark Error: {e}"


# ==================== 猫眼 API ====================

def get_maoyan_shows(cinema_id: str, city_id: str, movie_id: str) -> List[Dict]:
    url = "https://apis.netstart.cn/maoyan/cinema/shows"
    params = {"cinemaId": cinema_id, "ci": city_id, "channelId": 4}
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.38(0x1800262c) NetType/WIFI Language/zh_CN",
        "Referer": "https://m.maoyan.com/",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json()
        shows = []
        movies = data.get("data", {}).get("movies", []) or data.get("movies", [])
        for movie in movies:
            current_movie_id = str(movie.get("id", ""))
            movie_nm = movie.get("nm", "未知影片")
            if current_movie_id != movie_id:
                continue
            for date_info in movie.get("shows", []):
                show_date = date_info.get("dateShow", "")
                for show in date_info.get("plist", []):
                    shows.append({
                        "movie_id": current_movie_id,
                        "movie_name": movie_nm,
                        "show_date": show_date,
                        "show_time": show.get("tm", ""),
                        "hall": show.get("th", "未知影厅"),
                        "price": show.get("sellPrice", ""),
                        "lang": show.get("lang", ""),
                        "dim": show.get("dim", ""),
                    })
        return shows
    except Exception as e:
        print(f"[猫眼] 获取场次失败: {e}")
        return []


# ==================== 缓存管理 ====================

def load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_cache(cache: dict):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def make_key(show: dict) -> str:
    raw = f"{show['movie_id']}:{show['show_date']}:{show['show_time']}:{show['hall']}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ==================== 主逻辑 ====================

def main():
    print(f"\n{'='*60}")
    print(f"🎫 电影票监控运行 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"影院: MOViE MOViE影城(前滩太古里) | 电影ID: {MOVIE_ID}")
    print(f"监控日期: {len(MONITOR_DATES)} 个周末日期")
    print(f"{'='*60}")

    cache = load_cache()
    all_shows = get_maoyan_shows(CINEMA_ID, CITY_ID, MOVIE_ID)

    if not all_shows:
        print("未获取到场次数据，可能尚未放票或接口异常")
        return

    notified_any = False

    for monitor_date in MONITOR_DATES:
        date_shows = [s for s in all_shows if s["show_date"] == monitor_date]
        if not date_shows:
            continue

        known = cache.get(monitor_date, [])
        new_shows = []

        for show in date_shows:
            key = make_key(show)
            if key not in known:
                new_shows.append(show)
                known.append(key)

        if new_shows:
            cache[monitor_date] = known
            movie_nm = new_shows[0]["movie_name"]
            title = f"🎬 {movie_nm} 放票提醒"
            lines = [
                f"影院：MOViE MOViE影城(前滩太古里)",
                f"日期：{monitor_date}",
                f"发现 {len(new_shows)} 个新场次：",
                "",
            ]
            for show in new_shows:
                extra = f" {show.get('lang','')} {show.get('dim','')}".strip()
                lines.append(f"⏰ {show['show_time']} | {show['hall']}{extra} | ¥{show['price']}")
            body = "\n".join(lines)
            result = send_bark(title, body)
            print(f"  📅 {monitor_date}: 发现 {len(new_shows)} 个新场次 → {result}")
            notified_any = True
        else:
            print(f"  📅 {monitor_date}: 已有 {len(date_shows)} 个场次，暂无新增")

    save_cache(cache)

    if not notified_any:
        print("\n✅ 本次检查未发现新场次")
    else:
        print("\n🎉 已发送放票通知！")


if __name__ == "__main__":
    main()
