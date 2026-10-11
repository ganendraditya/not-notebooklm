import os
import sqlite3
import urllib.request
import csv
import logging

logger = logging.getLogger("uvicorn.error")

OPENJOURNALS_CSV_URL = "https://raw.githubusercontent.com/LukasRoeseler/openjournals/main/scimagojr_2024.csv"

def build_scopus_index_db(db_path: str) -> bool:
    """
    Downloads open-source Scopus SJR master dataset (~10MB CSV) and compiles
    it into an ultra-fast local SQLite lookup table (<0.1ms per query).
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    tmp_db_path = db_path + ".tmp"
    if os.path.exists(tmp_db_path):
        try:
            os.remove(tmp_db_path)
        except Exception:
            pass

    logger.info("[Scopus Indexer] Initializing Scopus master database from open-source registry...")
    try:
        req = urllib.request.Request(OPENJOURNALS_CSV_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            lines = [line.decode("utf-8", errors="ignore") for line in resp.readlines()]

        reader = csv.reader(lines, delimiter=";")
        _ = next(reader)

        conn = sqlite3.connect(tmp_db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE scopus_journals (issn TEXT PRIMARY KEY, quartile TEXT, sjr REAL, title TEXT)")

        rows = []
        for r in reader:
            if len(r) > 9:
                raw_issns = r[4]
                q = r[9].strip()
                if not q or q == "-":
                    continue

                # Filter out expired / discontinued journals whose coverage ended before active year (2024)
                if len(r) > 24:
                    cov = r[24].strip()
                    parts = [p.strip() for p in cov.split(",")[-1].split("-")]
                    last_year = parts[-1]
                    if last_year.isdigit() and int(last_year) < 2024:
                        continue  # Coverage expired / discontinued

                sjr_val = 0.0
                try:
                    sjr_str = r[8].strip().replace(",", ".")
                    sjr_val = float(sjr_str) if sjr_str else 0.0
                except Exception:
                    pass
                title_val = r[2].strip() if len(r) > 2 else ""

                for item in raw_issns.split(","):
                    clean = item.strip().replace("-", "").upper()
                    if len(clean) == 8:
                        rows.append((clean, q, sjr_val, title_val))

        cur.executemany("INSERT OR REPLACE INTO scopus_journals VALUES (?, ?, ?, ?)", rows)
        conn.commit()
        conn.close()

        os.replace(tmp_db_path, db_path)
        logger.info(f"[Scopus Indexer] Successfully compiled {len(rows)} Scopus journal records.")
        return True
    except Exception as e:
        logger.warning(f"[Scopus Indexer] Failed to auto-download Scopus master registry: {e}")
        if os.path.exists(tmp_db_path):
            try:
                os.remove(tmp_db_path)
            except Exception:
                pass
        return False
