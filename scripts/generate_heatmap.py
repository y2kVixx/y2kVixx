"""
Gera um heatmap estilo "GitHub contributions" a partir do histórico de
atividade (progresso de anime/mangá) de um usuário no AniList.

Uso:
    ANILIST_USERNAME=SeuUsuario python generate_heatmap.py

Saída:
    img/heatmap.svg
"""

import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

USERNAME = os.environ.get("ANILIST_USERNAME", "ASKKAAA")
DAYS_BACK = 365
OUTPUT_PATH = os.path.join("img", "heatmap.svg")

API_URL = "https://graphql.anilist.co"

QUERY = """
query ($userName: String, $page: Int) {
  Page(page: $page, perPage: 50) {
    pageInfo { hasNextPage }
    activities(userName: $userName, type_in: [ANIME_LIST, MANGA_LIST], sort: ID_DESC) {
      ... on ListActivity {
        createdAt
      }
    }
  }
}
"""


def fetch_activity(username, days_back):
    """Busca todas as atividades dos últimos `days_back` dias, paginando."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    cutoff_ts = int(cutoff.timestamp())

    counts = defaultdict(int)
    page = 1

    while True:
        payload = json.dumps(
            {"query": QUERY, "variables": {"userName": username, "page": page}}
        ).encode("utf-8")

        req = urllib.request.Request(
            API_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; anime-heatmap-bot/1.0)",
            },
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))

        page_data = body.get("data", {}).get("Page", {})
        activities = page_data.get("activities", [])

        if not activities:
            break

        stop = False
        for act in activities:
            ts = act.get("createdAt")
            if ts is None:
                continue
            if ts < cutoff_ts:
                stop = True
                continue
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            counts[date_str] += 1

        if stop or not page_data.get("pageInfo", {}).get("hasNextPage"):
            break

        page += 1

    return counts


def build_grid(counts, days_back):
    """Monta a grade de dias (colunas = semanas, linhas = dia da semana)."""
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=days_back)
    # alinha o início no domingo anterior, pra ficar igual ao GitHub
    start -= timedelta(days=(start.weekday() + 1) % 7)

    days = []
    d = start
    while d <= today:
        days.append(d)
        d += timedelta(days=1)

    weeks = [days[i : i + 7] for i in range(0, len(days), 7)]
    return weeks


def level_for(count, max_count):
    if count == 0 or max_count == 0:
        return 0
    ratio = count / max_count
    if ratio <= 0.25:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio <= 0.75:
        return 3
    return 4


COLORS = {
    0: "#1F1F23",  # sem atividade
    1: "#312E81",
    2: "#4338CA",
    3: "#6366F1",
    4: "#A5B4FC",
}

CELL = 11
GAP = 3
LEFT_PAD = 4
TOP_PAD = 4


def render_svg(weeks, counts):
    max_count = max(counts.values(), default=0)
    n_weeks = len(weeks)
    width = LEFT_PAD * 2 + n_weeks * (CELL + GAP)
    height = TOP_PAD * 2 + 7 * (CELL + GAP) + 20  # +20 pra legenda

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">',
        f'<rect width="100%" height="100%" fill="transparent"/>',
    ]

    for week_idx, week in enumerate(weeks):
        for day in week:
            date_str = day.strftime("%Y-%m-%d")
            count = counts.get(date_str, 0)
            lvl = level_for(count, max_count)
            color = COLORS[lvl]
            x = LEFT_PAD + week_idx * (CELL + GAP)
            # weekday() -> 0=segunda ... ajusta pra domingo ficar na linha 0
            y = TOP_PAD + ((day.weekday() + 1) % 7) * (CELL + GAP)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" ry="2" '
                f'fill="{color}"><title>{date_str}: {count} atividade(s)</title></rect>'
            )

    # legenda "Less -> More"
    legend_y = height - 14
    legend_x = LEFT_PAD
    parts.append(
        f'<text x="{legend_x}" y="{legend_y + 9}" font-size="10" fill="#8B8B93" '
        f'font-family="sans-serif">Menos</text>'
    )
    lx = legend_x + 42
    for lvl in range(5):
        parts.append(
            f'<rect x="{lx}" y="{legend_y}" width="{CELL}" height="{CELL}" rx="2" ry="2" '
            f'fill="{COLORS[lvl]}"/>'
        )
        lx += CELL + GAP
    parts.append(
        f'<text x="{lx + 4}" y="{legend_y + 9}" font-size="10" fill="#8B8B93" '
        f'font-family="sans-serif">Mais</text>'
    )

    parts.append("</svg>")
    return "\n".join(parts)


def main():
    counts = fetch_activity(USERNAME, DAYS_BACK)
    weeks = build_grid(counts, DAYS_BACK)
    svg = render_svg(weeks, counts)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"Heatmap gerado com {sum(counts.values())} atividades em {len(counts)} dias distintos.")
    print(f"Salvo em: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
