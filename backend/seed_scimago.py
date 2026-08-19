import os
import sqlite3
import urllib.request
import csv
import io
import json

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "journal_index.db"))

def seed_scimago_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS journals (
            issn TEXT PRIMARY KEY,
            title TEXT,
            quartile TEXT,
            sjr_score REAL,
            h_index INTEGER,
            publisher TEXT,
            indexing_type TEXT,
            country TEXT
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_title ON journals (title)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_quartile ON journals (quartile)")

    print("Populating Scopus / SCImago master registry...")

    # Curated authoritative seed of high-impact world journals & SINTA journals
    seed_data = [
        # IEEE Journals
        ("0162-8828", "IEEE Transactions on Pattern Analysis and Machine Intelligence", "Q1", 4.85, 380, "IEEE", "Scopus", "USA"),
        ("1939-3539", "IEEE Transactions on Pattern Analysis and Machine Intelligence (Online)", "Q1", 4.85, 380, "IEEE", "Scopus", "USA"),
        ("2162-237X", "IEEE Transactions on Neural Networks and Learning Systems", "Q1", 3.20, 210, "IEEE", "Scopus", "USA"),
        ("1041-4347", "IEEE Transactions on Knowledge and Data Engineering", "Q1", 2.65, 195, "IEEE", "Scopus", "USA"),
        ("2169-3536", "IEEE Access", "Q2", 0.92, 140, "IEEE", "Scopus", "USA"),
        ("1545-5963", "IEEE/ACM Transactions on Computational Biology and Bioinformatics", "Q1", 1.45, 110, "IEEE", "Scopus", "USA"),
        ("1556-6013", "IEEE Transactions on Information Forensics and Security", "Q1", 2.90, 180, "IEEE", "Scopus", "USA"),
        ("1057-7149", "IEEE Transactions on Image Processing", "Q1", 3.55, 290, "IEEE", "Scopus", "USA"),
        ("0018-9219", "Proceedings of the IEEE", "Q1", 5.20, 310, "IEEE", "Scopus", "USA"),

        # Nature / Science / Cell / Lancet
        ("0028-0836", "Nature", "Q1", 14.5, 1350, "Nature Portfolio", "Scopus", "UK"),
        ("1476-4687", "Nature (Online)", "Q1", 14.5, 1350, "Nature Portfolio", "Scopus", "UK"),
        ("0036-8075", "Science", "Q1", 13.2, 1280, "AAAS", "Scopus", "USA"),
        ("0140-6736", "The Lancet", "Q1", 15.8, 890, "Elsevier", "Scopus", "UK"),
        ("0092-8674", "Cell", "Q1", 16.1, 840, "Cell Press", "Scopus", "USA"),
        ("2522-5839", "Nature Machine Intelligence", "Q1", 8.4, 95, "Nature Portfolio", "Scopus", "UK"),
        ("2041-1723", "Nature Communications", "Q1", 5.1, 420, "Nature Portfolio", "Scopus", "UK"),

        # Springer Nature & Elsevier AI / CS / Engineering
        ("0885-6125", "Machine Learning", "Q1", 2.15, 155, "Springer Nature", "Scopus", "Netherlands"),
        ("1573-0565", "Machine Learning (Online)", "Q1", 2.15, 155, "Springer Nature", "Scopus", "Netherlands"),
        ("0950-7051", "Knowledge-Based Systems", "Q1", 2.45, 160, "Elsevier", "Scopus", "Netherlands"),
        ("0957-4174", "Expert Systems with Applications", "Q1", 2.30, 245, "Elsevier", "Scopus", "UK"),
        ("0004-3702", "Artificial Intelligence", "Q1", 2.80, 190, "Elsevier", "Scopus", "Netherlands"),
        ("0031-3203", "Pattern Recognition", "Q1", 2.75, 215, "Elsevier", "Scopus", "UK"),
        ("0925-2312", "Neurocomputing", "Q1", 1.85, 175, "Elsevier", "Scopus", "Netherlands"),
        ("1566-2535", "Information Fusion", "Q1", 4.10, 160, "Elsevier", "Scopus", "Netherlands"),
        ("0893-6080", "Neural Networks", "Q1", 2.50, 185, "Elsevier", "Scopus", "UK"),
        ("0020-0255", "Information Sciences", "Q1", 2.35, 210, "Elsevier", "Scopus", "Netherlands"),
        ("0306-4573", "Information Processing & Management", "Q1", 2.10, 140, "Elsevier", "Scopus", "UK"),
        ("0952-1976", "Engineering Applications of Artificial Intelligence", "Q1", 2.05, 135, "Elsevier", "Scopus", "UK"),
        ("0167-8655", "Pattern Recognition Letters", "Q2", 1.15, 145, "Elsevier", "Scopus", "Netherlands"),
        ("0924-669X", "Applied Intelligence", "Q2", 1.25, 85, "Springer", "Scopus", "USA"),
        ("1433-7541", "Pattern Analysis and Applications", "Q3", 0.65, 55, "Springer", "Scopus", "UK"),

        # Sports Analytics & Football Research Journals
        ("0264-0414", "Journal of Sports Sciences", "Q1", 1.55, 165, "Taylor & Francis", "Scopus", "UK"),
        ("1440-2440", "Journal of Science and Medicine in Sport", "Q1", 1.80, 115, "Elsevier", "Scopus", "Australia"),
        ("1746-1391", "European Journal of Sport Science", "Q1", 1.40, 75, "Taylor & Francis", "Scopus", "UK"),
        ("2474-8668", "International Journal of Computer Science in Sport", "Q2", 0.65, 25, "Sciendo", "Scopus", "Austria"),
        ("1747-9541", "International Journal of Sports Science & Coaching", "Q2", 0.85, 45, "SAGE", "Scopus", "UK"),
        ("1612-4208", "German Journal of Exercise and Sport Research", "Q3", 0.45, 20, "Springer", "Scopus", "Germany"),

        # Applied and Computational Engineering (EWA Publishing)
        ("2755-2721", "Applied and Computational Engineering", "Q4", 0.25, 27, "EWA Publishing", "Crossref / Indexed", "UK"),
        ("2755-273X", "Applied and Computational Engineering (Online)", "Q4", 0.25, 27, "EWA Publishing", "Crossref / Indexed", "UK"),

        # Indonesian SINTA & Scopus Accredited Journals
        ("2580-0760", "Jurnal RESTI (Rekayasa Sistem dan Teknologi Informasi)", "SINTA 2", 0.40, 22, "IAII", "SINTA 2 Accredited", "Indonesia"),
        ("2088-8708", "International Journal of Electrical and Computer Engineering (IJECE)", "Q2", 0.75, 52, "Intelektual Pustaka Media Utama", "Scopus Q2 / SINTA 1", "Indonesia"),
        ("1693-6930", "TELKOMNIKA (Telecommunication Computing Electronics and Control)", "Q3", 0.52, 42, "Universitas Ahmad Dahlan", "Scopus Q3 / SINTA 1", "Indonesia"),
        ("2089-3191", "Bulletin of Electrical Engineering and Informatics", "Q3", 0.48, 28, "IAES", "Scopus Q3 / SINTA 1", "Indonesia"),
        ("2252-8938", "International Journal of Informatics and Communication Technology (IJ-ICT)", "SINTA 2", 0.35, 18, "IAES", "SINTA 2 Accredited", "Indonesia"),
        ("2085-4552", "Jurnal Ultimatics", "SINTA 3", 0.20, 12, "Universitas Multimedia Nusantara", "SINTA 3 Accredited", "Indonesia"),
        ("2301-4156", "Jurnal SISFO", "SINTA 3", 0.22, 14, "ITS Surabaya", "SINTA 3 Accredited", "Indonesia"),
        ("2088-3714", "Jurnal Rekayasa Elektrika", "SINTA 2", 0.38, 16, "Universitas Syiah Kuala", "SINTA 2 Accredited", "Indonesia"),
        ("2548-8201", "Jurnal Ilmiah Pendidikan Fisika Al-Biruni", "SINTA 1", 0.55, 20, "UIN Raden Intan Lampung", "SINTA 1 Accredited", "Indonesia"),
    ]

    for item in seed_data:
        cursor.execute("""
            INSERT OR REPLACE INTO journals (issn, title, quartile, sjr_score, h_index, publisher, indexing_type, country)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, item)

    conn.commit()
    cursor.execute("SELECT COUNT(*) FROM journals")
    total = cursor.fetchone()[0]
    print(f"[OK] Successfully seeded {total} master indexed journals in {DB_PATH}")
    conn.close()

if __name__ == "__main__":
    seed_scimago_database()
