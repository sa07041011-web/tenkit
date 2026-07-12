# -*- coding: utf-8 -*-
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 朝の天気 & 災害情報 LINE通知スクリプト(石狩市版)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

このプログラムがやること:
  【朝の実行】 天気予報 + 警報・注意報をLINEに送る
  【昼の実行】 警報・注意報が出ていれば LINEに送る(何もなければ送らない)

データの取得元は「気象庁」の公式サイトです(無料・登録不要)。

★ このファイルを自分で書き換える必要は基本的にありません ★
"""

import os
import sys
import json
import urllib.request
from datetime import datetime, timezone, timedelta

# ============================================================
# 設定(石狩市用にすでに設定済み。変えなくてOK)
# ============================================================

# 気象庁の「地方」コード: 016000 = 石狩・空知・後志地方
OFFICE_CODE = "016000"

# 予報区の名前: 石狩市は「石狩地方」に含まれます
FORECAST_AREA_NAME = "石狩"

# 市町村コード: 0123500 = 石狩市(警報・注意報の確認に使う)
CITY_CODE = "0123500"
CITY_NAME = "石狩市"

# LINEに送るための情報(GitHubのSecretsから自動で読み込まれる)
LINE_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_USER_ID = os.environ["LINE_USER_ID"]

# 日本時間
JST = timezone(timedelta(hours=9))

# ============================================================
# 警報・注意報のコード表(気象庁の番号 → 日本語名)
# ============================================================
WARNING_NAMES = {
    "33": "🚨大雨特別警報", "35": "🚨暴風特別警報", "32": "🚨暴風雪特別警報",
    "36": "🚨大雪特別警報", "37": "🚨波浪特別警報", "38": "🚨高潮特別警報",
    "03": "⚠️大雨警報", "04": "⚠️洪水警報", "05": "⚠️暴風警報",
    "02": "⚠️暴風雪警報", "06": "⚠️大雪警報", "07": "⚠️波浪警報",
    "08": "⚠️高潮警報",
    "10": "🟡大雨注意報", "18": "🟡洪水注意報", "15": "🟡強風注意報",
    "13": "🟡風雪注意報", "12": "🟡大雪注意報", "16": "🟡波浪注意報",
    "19": "🟡高潮注意報", "14": "🟡雷注意報", "20": "🟡濃霧注意報",
    "21": "🟡乾燥注意報", "22": "🟡なだれ注意報", "23": "🟡低温注意報",
    "24": "🟡霜注意報", "25": "🟡着氷注意報", "26": "🟡着雪注意報",
    "17": "🟡融雪注意報",
}


def get_json(url):
    """インターネットからデータを取ってくる共通の関数"""
    with urllib.request.urlopen(url) as res:
        return json.loads(res.read().decode())


def find_area(areas, keyword):
    """予報データの中から「石狩」を含む地域を探す。見つからなければ先頭を使う"""
    for area in areas:
        if keyword in area["area"]["name"]:
            return area
    return areas[0]


# ============================================================
# ① 天気予報を取得する
# ============================================================
def fetch_weather():
    url = f"https://www.jma.go.jp/bosai/forecast/data/forecast/{OFFICE_CODE}.json"
    data = get_json(url)
    forecast = data[0]  # 短期予報(今日〜明後日)

    # 天気(例: 「くもり 時々 晴れ」)
    weather_area = find_area(forecast["timeSeries"][0]["areas"], FORECAST_AREA_NAME)
    weather_today = weather_area["weathers"][0]

    # 降水確率(6時間ごと)
    pop_area = find_area(forecast["timeSeries"][1]["areas"], FORECAST_AREA_NAME)
    pops = [p for p in pop_area["pops"] if p != ""]
    pop_text = " / ".join(p + "%" for p in pops)

    # 気温(最低/最高)※観測地点は札幌になります
    temp_area = forecast["timeSeries"][2]["areas"][0]
    temps = [t for t in temp_area["temps"] if t != ""]
    temp_text = ""
    if len(temps) >= 2:
        temp_text = f"\n🌡 気温: {temps[0]}℃ 〜 {temps[1]}℃"

    today = datetime.now(JST).strftime("%m月%d日")
    return (
        f"☀️ おはようございます!\n"
        f"【{today} {CITY_NAME}周辺の天気】\n"
        f"{weather_today}\n"
        f"☔️ 降水確率: {pop_text}"
        f"{temp_text}"
    )


# ============================================================
# ② 警報・注意報を取得する(大雨・豪雨などの災害情報)
# ============================================================
def fetch_warnings():
    """石狩市に出ている警報・注意報のリストを返す。何もなければ空のリスト"""
    url = f"https://www.jma.go.jp/bosai/warning/data/warning/{OFFICE_CODE}.json"
    data = get_json(url)

    active = []
    # データの中から石狩市(0123500)を探す
    for area_type in data.get("areaTypes", []):
        for area in area_type.get("areas", []):
            if area.get("code") != CITY_CODE:
                continue
            for w in area.get("warnings", []):
                # 「発表」「継続」中のものだけを対象にする(「解除」は無視)
                if w.get("status") in ("発表", "継続") and w.get("code"):
                    name = WARNING_NAMES.get(w["code"], f"警報・注意報(コード{w['code']})")
                    if name not in active:
                        active.append(name)
    return active


def warnings_message(active):
    now = datetime.now(JST).strftime("%m月%d日 %H:%M")
    lines = "\n".join("・" + name for name in active)
    return (
        f"📢【{CITY_NAME}に気象情報が出ています】\n"
        f"({now} 時点)\n"
        f"{lines}\n\n"
        f"最新情報は気象庁サイトで確認してください:\n"
        f"https://www.jma.go.jp/bosai/warning/#area_type=class20s&area_code={CITY_CODE}"
    )


# ============================================================
# ③ LINEにメッセージを送る
# ============================================================
def send_line(message):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}",
    }
    body = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": message}]}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req) as res:
        print("LINE送信しました(ステータス:", res.status, ")")


# ============================================================
# メイン処理
#   morning → 天気 + 警報を送る
#   noon    → 警報が出ているときだけ送る
# ============================================================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    warnings = fetch_warnings()

    if mode == "morning":
        msg = fetch_weather()
        if warnings:
            msg += "\n\n" + warnings_message(warnings)
        send_line(msg)

    else:  # noon(昼のチェック)
        if warnings:
            send_line(warnings_message(warnings))
        else:
            print("警報・注意報は出ていません。昼の通知はスキップします。")
