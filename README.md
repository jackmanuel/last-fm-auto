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

## Setup and Installation

**Note:** It is highly recommended to use a Python virtual environment.

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/jackmanuel/last-fm-auto.git
    cd last-fm-auto
    ```
2.  **Install the project in editable mode**:
    This command uses the `setup.py` file to install the project package and its dependencies. The `-e` flag makes the installation "editable," so any code changes are immediately available.
    ```bash
    pip install -e .
    ```
3.  **Configure Environment and Database**:
    
    First, create a `.env` file in the root directory. Edit the `.env` file with your credentials and path to your database.
    ```
    LAST_FM_API_KEY="your_api_key"
    LAST_FM_API_SECRET="your_api_secret"
    LAST_FM_SESSION_KEY="your_session_key"
    DATABASE_PATH="C:/path/to/your/database.db"
    GUILD_ID="your_discord_guild_id"
    ```
    
    **Setting Up Last.fm Session Key**

    To scrobble tracks to Last.fm, you need to authenticate your application. This is a one-time setup process that uses OAuth to securely connect with Last.fm.

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
    
    Your database must contain a table named `play_history` with the following columns:
    
    | Column Name | Data Type | Description |
    | :--- | :--- | :--- |
    | `request_id` | INTEGER | A unique identifier for the row. |
    | `query` | TEXT | The raw song title to be searched for (can be a YouTube Link). |
    | `resolved_title` | TEXT | The resolved title of the YouTube video returned. |
    | `channel_name` | TEXT | The YouTube channel/uploader name. This can be null or empty, but the column must exist for the main scrobbler. |
    | `guild_id` | TEXT | The guild id of the server that should be scrobbled. |
    | `play_start_timestamp` | TEXT | The UTC timestamp when the song started playing (eg. 2024-11-01T17:02:49.765055). |
    | `duration` | INTEGER | The duration of the song in seconds. |
    | `play_status` | TEXT | The playback status. This is either `playing` or `completed`. |
    | `scrobble_status` | TEXT | The scrobble processing status. This is either `new`, `scrobbled`, or `failed`. |

    **Integration Flexibility**

    While this project was developed to work with the [python-music-bot](https://github.com/jackmanuel/python-music-bot), it is designed to be data-source agnostic. Any application can use this scrobbler as long as it can populate a SQLite database with a `play_history` table that matches the schema described above.

    For YouTube URL rows, `channel_name` is used only when it can be matched confidently to an artist in `data/artists.json`. If the value is missing, empty, noisy, ambiguous, or below the configured thresholds, the pipeline ignores it and falls back to the normal resolved-title matching strategies.

## Usage

### Running the Scrobbler

The primary way to run the application is by using the provided batch script. This will start the main process that monitors the database for pending tracks. It will check the database for new entries every 5 seconds by default.

```bash
# From the project root directory
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

These scripts are for development, testing, and data preparation. Because the project is installed as a package, you must run them with the `python -m` flag from the project's root directory.

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
