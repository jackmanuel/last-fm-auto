
import sqlite3
import csv
import pandas as pd
import argparse

def is_youtube_url(url):
    """Checks if a URL is a YouTube URL."""
    if not isinstance(url, str):
        return False
    return "youtube.com" in url or "youtu.be" in url

def get_youtube_channel(row):
    """Returns the YouTube channel name stored by python-music-bot."""
    if pd.isna(row["channel_name"]):
        return ""

    return str(row["channel_name"])

def create_ground_truth_csv(db_path, csv_path):
    """
    Creates a ground truth CSV file by extracting YouTube queries from a database.

    Args:
        db_path (str): The path to the input SQLite database file.
        csv_path (str): The path for the output CSV file.
    """
    try:
        conn = sqlite3.connect(db_path)
        query = "SELECT request_id, query, resolved_title, resolved_url, channel_name FROM play_history"
        df = pd.read_sql_query(query, conn)
        conn.close()
    except (sqlite3.Error, pd.io.sql.DatabaseError) as e:
        print(f"Error accessing the database at '{db_path}': {e}")
        return

    youtube_queries = df[df["query"].apply(is_youtube_url)].copy()
    before_dedup = len(youtube_queries)
    youtube_queries = youtube_queries.drop_duplicates(subset=["query"], keep="first")
    removed_duplicates = before_dedup - len(youtube_queries)

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["id", "query", "resolved_title", "url", "youtube_channel", "track_gt", "artist_gt"])
            for index, row in youtube_queries.iterrows():
                writer.writerow([
                    row["request_id"],
                    row["query"],
                    row["resolved_title"],
                    row["resolved_url"],
                    get_youtube_channel(row),
                    "",
                    "",
                ])
        print(f"Ground truth data successfully written to '{csv_path}'")
        if removed_duplicates:
            print(f"Skipped {removed_duplicates} duplicate YouTube queries.")
    except IOError as e:
        print(f"Error writing to CSV file at '{csv_path}': {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a ground truth CSV file from a play history database by filtering for YouTube URLs."
    )
    parser.add_argument(
        "db_path", 
        help="Path to the input SQLite database file."
    )
    parser.add_argument(
        "csv_path", 
        help="Path to the output CSV file."
    )
    
    args = parser.parse_args()
    
    create_ground_truth_csv(args.db_path, args.csv_path)
