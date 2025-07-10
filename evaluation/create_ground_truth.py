
import sqlite3
import csv
import pandas as pd

def is_youtube_url(url):
    return "youtube.com" in url or "youtu.be" in url

def create_ground_truth_csv():
    db_path = r"C:/Users/Jack/Documents/Discord Last.fm Account/last-fm-auto/music_log_old.db"
    csv_path = r"C:/Users/Jack/Documents/Discord Last.fm Account/last-fm-auto/evaluation/ground_truth_data_yt_v2.csv"

    conn = sqlite3.connect(db_path)
    query = "SELECT request_id, query, resolved_title, resolved_url FROM play_history"
    df = pd.read_sql_query(query, conn)
    conn.close()

    youtube_queries = df[df["query"].apply(is_youtube_url)]

    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["id", "query", "resolved_title", "url", "track_gt", "artist_gt"])
        for index, row in youtube_queries.iterrows():
            writer.writerow([row["request_id"], row["query"], row["resolved_title"], row["resolved_url"], "", ""])

if __name__ == "__main__":
    create_ground_truth_csv()
