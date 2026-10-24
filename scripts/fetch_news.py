"""Descarga los feeds RSS de economía y genera news.json para argecon.ar.

Lo corre la GitHub Action .github/workflows/news.yml cada 15 minutos.
La página lee /news.json (mismo dominio: sin CORS ni servicios intermedios).
Si un feed falla o viene vacío se saltea; si fallan todos, no se pisa
el news.json anterior.
"""
import calendar
import json
import os
import re
import sys
from datetime import datetime, timezone

import feedparser

FEEDS = [
    ("Ámbito", "https://www.ambito.com/rss/pages/economia.xml"),
    ("iProfesional", "https://www.iprofesional.com/rss/economia"),
    ("Infobae", "https://www.infobae.com/arc/outboundfeeds/rss/category/economia/"),
    ("Clarín", "https://www.clarin.com/rss/economia/"),
    ("La Gaceta", "https://www.lagaceta.com.ar/rss/seccion/economia/"),
    # Bloomberg Línea (Arc XP): se prueba la sección Argentina y, si no hay, el feed general
    ("Bloomberg Línea", [
        "https://www.bloomberglinea.com/arc/outboundfeeds/rss/category/latinoamerica/argentina/?outputType=xml",
        "https://www.bloomberglinea.com/arc/outboundfeeds/rss/?outputType=xml",
    ]),
]
PER_FEED = 8
MAX_ITEMS = 30
UA = "Mozilla/5.0 (compatible; argecon.ar news fetcher; +https://argecon.ar)"
# Notas de cotizaciones de otros países (ej. "Euro hoy en Venezuela"): no aportan
EXCLUDE = re.compile(
    r"^(Euro|Dólar|Dolar|Real|Peso|Libra|Yuan|Yen|Bitcoin)\b.*\bhoy en (?!Argentina\b)[A-ZÁÉÍÓÚ]"
)
OUT = os.path.join(os.path.dirname(__file__), "..", "news.json")


def main():
    items, ok = [], []
    for source, urls in FEEDS:
        d = None
        for url in [urls] if isinstance(urls, str) else urls:
            try:
                d = feedparser.parse(url, agent=UA)
            except Exception as e:  # noqa: BLE001
                print(f"[{source}] error {url}: {e}", file=sys.stderr)
                continue
            print(f"[{source}] {url} -> status={d.get('status')} entries={len(d.entries)}", file=sys.stderr)
            if d.entries:
                break
        if d is None:
            continue
        n = 0
        for e in d.entries[:PER_FEED]:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            if not title or not link.startswith("http") or EXCLUDE.search(title):
                continue
            t = e.get("published_parsed") or e.get("updated_parsed")
            pub = (
                datetime.fromtimestamp(calendar.timegm(t), timezone.utc).isoformat()
                if t else ""
            )
            items.append({"title": title, "link": link, "source": source, "pubDate": pub})
            n += 1
        print(f"[{source}] {n} items (bozo={d.get('bozo')})", file=sys.stderr)
        if n:
            ok.append(source)

    if not items:
        print("Ningún feed respondió: se conserva el news.json anterior", file=sys.stderr)
        return

    # Sin duplicados por título, más recientes primero
    seen, uniq = set(), []
    for it in items:
        k = it["title"].lower()
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    uniq.sort(key=lambda x: x["pubDate"], reverse=True)

    data = {"sources": ok, "items": uniq[:MAX_ITEMS]}
    new = json.dumps(data, ensure_ascii=False, indent=1)
    try:
        with open(OUT, encoding="utf-8") as f:
            if json.loads(f.read()) == data:
                print("Sin cambios", file=sys.stderr)
                return
    except (FileNotFoundError, ValueError):
        pass
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(new + "\n")
    print(f"news.json actualizado: {len(data['items'])} noticias", file=sys.stderr)


if __name__ == "__main__":
    main()
