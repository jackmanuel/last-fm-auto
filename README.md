# Last.fm Auto-Scrobbler

This project provides a sophisticated pipeline for automatically scrobbling tracks to Last.fm, designed to work in tandem with the [python-music-bot](https://github.com/jackmanuel/python-music-bot). It takes raw, often messy, song titles (e.g., from a search query or a YouTube title) and intelligently finds the correct track on Last.fm using a multi-step, configurable pipeline.

## Key Features

*   **Advanced Title Cleaning**: A robust preprocessing pipeline that cleans and standardizes input queries.
*   **Local Database Cache**: An optional local track database for instantly matching common/problematic tracks without hitting the Last.fm API.
*   **Artist/Track Splitting**: A fuzzy matching step that can split queries like `track artist` into structured artist and track values before searching.
*   **YouTube Channel Artist Hints**: For YouTube URL requests, the pipeline can use the video's channel name as a strict artist hint when the resolved title does not already contain a clear artist signal.
*   **Intelligent API Searching**: A scoring model that balances string similarity and track popularity to find the best match.
*   **Configurable Pipeline**: Easily tune weights, thresholds, and other parameters in the `config.py` file.
*   **Comprehensive Evaluation Framework**: There are scripts to test, tune, and validate the accuracy of the matching algorithm.

## Project Structure

*   `last_fm_auto/`: The core Python package.
    *   `main.py`: The main entry point for running the scrobbler.
    *   `pipeline.py`: Orchestrates the track-finding process.
    *   `scoring.py`: Contains the core logic for scoring and selecting tracks.
    *   `preprocessing.py`: Handles all text cleaning and normalization.
    *   `lastfm_client.py`: Manages all communication with the Last.fm API.
    *   `config.py`: Central configuration for all pipeline parameters.
*   `evaluation/`: Scripts for model tuning, splitting evaluation, and accuracy evaluation.
*   `scripts/`: Helper scripts for tasks like building the local track database and curating artist data.
*   `data/`: Data files, such as the abbreviation list, artist list, local track database, and evaluation ground truth.

See [Data Provenance and Licence](data/README.md#data-provenance-and-licence) for the source of the bundled artist list and how the MIT licence applies.


## Setup and Installation

Setup was verified with Python 3.13. A virtual environment is recommended.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/jackmanuel/last-fm-auto.git
    cd last-fm-auto
    ```
2.  **Create a virtual environment and install dependencies**:
    On Windows, use PowerShell:
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
    ```
    On macOS or Linux:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    python -m pip install -r requirements.txt
    ```
    Run the commands below from the project root. On Windows, use `.\.venv\Scripts\python.exe` in place of `python`.
3.  **Configure Environment and Database**:
    
    Copy `.env.example` to a new file named `.env` in the root directory:
    ```bash
    cp .env.example .env
    ```
    In PowerShell, use `Copy-Item .env.example .env`.
    
    Edit the `.env` file with your credentials and path to your database.
    ```
    LAST_FM_API_KEY="your_api_key"
    LAST_FM_API_SECRET="your_api_secret"
    LAST_FM_SESSION_KEY=""
    DATABASE_PATH="C:/path/to/your/database.db"
    SCROBBLE_MODE="guild"
    GUILD_ID="your_discord_guild_id"
    ```

    Guild mode is the default when `SCROBBLE_MODE` is omitted. It requires `GUILD_ID` and only reads plays from that Discord server.

    
    **Setting Up Last.fm Session Key**

    To scrobble tracks to Last.fm, authorize the application once using Last.fm's desktop authentication flow.

    1.  **Get Last.fm API Credentials**:
        -   Go to the [Last.fm API page](https://www.last.fm/api/account/create) to create an API account.
        -   Once you have your `API_KEY` and `API_SECRET`, add them to the `.env` file.

    2.  **Generate a Session Key**:
        Run the following command from the project root:
        ```bash
        python -m last_fm_auto.main --authenticate
        ```
        This script will:
        -   Provide a URL for you to open in your browser.
        -   Ask you to authorize the application on the Last.fm website.
        -   Once authorized, it will automatically fetch the session key and save it to your `.env` file.

        You only need to do this once. The scrobbler will use the saved session key for all future operations.

    **Database Requirements**
    
    The application requires `DATABASE_PATH` to point to a SQLite database with a specific structure. The script reads from a table of pending tracks to scrobble.
    
    Your database must contain a table named `play_history` with the columns below. Only guild mode requires `guild_id`.
    
    | Column Name | Data Type | Description |
    | :--- | :--- | :--- |
    | `request_id` | INTEGER | A unique identifier for the row. |
    | `query` | TEXT | The raw song title to be searched for (can be a YouTube Link). |
    | `resolved_title` | TEXT | The resolved title of the YouTube video returned. |
    | `channel_name` | TEXT | The YouTube channel/uploader name. This can be null or empty, but the column must exist for the main scrobbler. |
    | `guild_id` | TEXT | In guild mode, the Discord server ID associated with the play. |
    | `play_start_timestamp` | TEXT | The UTC timestamp when the song started playing (e.g., 2024-11-01T17:02:49.765055). |
    | `duration` | INTEGER | The duration of the song in seconds. |
    | `play_status` | TEXT | The playback status. Supported values: `queued`, `playing`, `completed`, `skipped`. |
    | `scrobble_status` | TEXT | The scrobble processing status. Supported values: `new`, `scrobbled`, `failed`. |

    **Additional Columns (Optional)**

    If you are integrating with [python-music-bot](https://github.com/jackmanuel/python-music-bot), the database schema will contain the following columns which are ignored by the scrobbler but required by the bot:
    
    | Column Name | Data Type | Description |
    | :--- | :--- | :--- |
    | `request_timestamp` | TEXT | The UTC timestamp when the playback request was made. |
    | `user_id` | TEXT | The Discord user ID of the requesting user. |
    | `user_name` | TEXT | The Discord username of the requesting user. |
    | `resolved_url` | TEXT | The resolved video or stream URL. |

    **Standalone SQLite Setup**

    To use playback history from another application, set `SCROBBLE_MODE="standalone"`, unset `GUILD_ID`, and point `DATABASE_PATH` to a dedicated SQLite database. Standalone mode processes all eligible plays in that database, so use guild mode for a shared Discord bot database. The source application supplies playback rows and the scrobbler writes their `scrobble_status` back to the table.

    For YouTube URL rows, `channel_name` is used only when it can be matched confidently to an artist in `data/artists.json`. If the value is missing, empty, noisy, ambiguous, or below the configured thresholds, the pipeline ignores it and falls back to the normal resolved-title matching strategies.

    To create an empty standalone `play_history` table, run this SQL in SQLite:

    ```sql
    CREATE TABLE play_history (
        request_id INTEGER PRIMARY KEY,
        query TEXT,
        resolved_title TEXT,
        channel_name TEXT,
        play_start_timestamp TEXT,
        duration INTEGER,
        play_status TEXT,
        scrobble_status TEXT
    );
    ```

    After authenticating, run `python -m last_fm_auto.main --run-once`. With an empty table, it should report that there are no new songs to process. To queue a scrobble, add a row with `play_status='completed'` and `scrobble_status='new'`.

## Usage

### Running the Scrobbler

Run the scrobbler from the project root to monitor the database for pending tracks. It checks for new entries every 5 seconds by default.

```bash
python -m last_fm_auto.main
```

On Windows, you can also use the batch script to start it with the project's virtual environment.

```powershell
.\run_scrobbler.bat
```

### Query Format Tips

For plain text queries, the current artist/track splitter works best when users put the track first and the artist at the end:

```text
sometimes mbv
i will beatles
lean beef patty jpegmafia
```

Dash-separated queries are more flexible because the splitter checks both sides and uses whichever side looks more like an artist:

```text
The Beatles - I Will
I Will - The Beatles
```

Artist-first plain text queries such as `beatles i will` are not currently handled as well. They may still work through the fallback Last.fm search, but `track artist` is the preferred format for best results.

### Helper Scripts

Run these development, testing, and data preparation scripts with `python -m` from the project root.

*   **Build the Artist List**:
    Generate `data/artists.json` from the source CSV files. This is used by the query splitter to recognize artist names.
    ```bash
    python -m scripts.build_artist_list
    ```
*   **Curate Comma-Containing Artists**:
    Review artist names that contain commas and mark whether they are real artist names or collaboration-style noise. The build script uses this curation when regenerating `data/artists.json`.
    ```bash
    python -m scripts.curate_comma_artists
    ```
*   **Build the Local Track Database (Optional)**:
    Generate a local searchable JSON file from your source CSVs. For details on the required CSV format, see `data/README.md`.
    ```bash
    python -m scripts.build_searchable_tracks
    ```
*   **Test a Single Query**:
    Test the entire pipeline with a single song title.
    ```bash
    python -m scripts.test_query --query "Your Song Title Here"
    ```
    To test YouTube URL fallback behaviour, include the resolved video title and, optionally, the uploader/channel name:
    ```bash
    python -m scripts.test_query --query "https://www.youtube.com/watch?v=example" --resolved-title "Song Title" --youtube-channel "Artist - Topic"
    ```

## Evaluation and Tuning

This project includes an evaluation suite for two related parts of matching:

*   tuning the weighted Last.fm search-result scorer, which balances string similarity and listener popularity;
*   evaluating the pre-search artist/track splitter, which decides whether a raw query contains an artist name.

For more details on the process and how to run the tuning scripts, see the `evaluation/README.md` file.
