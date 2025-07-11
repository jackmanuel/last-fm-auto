# Last.fm Auto-Scrobbler

This project provides a sophisticated pipeline for automatically scrobbling tracks to Last.fm. It is designed to take raw, often messy, song titles (e.g., from a Discord bot or a YouTube video) and intelligently find the correct track on Last.fm using a multi-step, configurable pipeline.

## Key Features

*   **Advanced Title Cleaning**: A robust preprocessing pipeline that cleans and standardizes input queries.
*   **Local Database Cache**: An optional local track database for instantly matching common/problematic tracks without hitting the Last.fm API.
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
*   `evaluation/`: Scripts for model tuning and accuracy evaluation.
*   `scripts/`: Helper scripts for tasks like building the local track database.
*   `data/`: Data files, such as the abbreviation list and local track database.

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
    
    First, create a `.env` file in the root directory by copying the example:
    ```bash
    # For Windows
    copy .env.example .env

    # For macOS/Linux
    cp .env.example .env
    ```
    Next, edit the new `.env` file with your credentials and path to your database.
    ```
    LAST_FM_API_KEY="your_api_key"
    LAST_FM_API_SECRET="your_api_secret"
    LAST_FM_SESSION_KEY="your_session_key"
    DATABASE_PATH="C:/path/to/your/database.db"
    GUILD_ID="your_discord_guild_id"
    ```
    
    **Database Requirements**
    
    The application requires `DATABASE_PATH` to point to a SQLite database with a specific structure. The script reads from a table of pending tracks to scrobble.
    
    Your database must contain a table named `play_history` with the following columns:
    
    | Column Name | Data Type | Description |
    | :--- | :--- | :--- |
    | `request_id` | INTEGER | A unique identifier for the row. |
    | `query` | TEXT | The raw song title to be searched for (can be a YouTube Link). |
    | `resolved_title` | Text | The resolved title of the YouTube video returned. |
    | `guild_id` | TEXT | The guild id of the server that should be scrobbled. |
    | `timestamp` | TEXT | The timestamp that the song will be scrobbled at (eg. 2024-11-01T17:02:49.765055) Must be UTC.
    | `status` | TEXT | The processing status. This is either `new`, `scrobbled`, or `failed`.|

## Usage

### Running the Scrobbler

The primary way to run the application is by using the provided batch script. This will start the main process that monitors the database for pending tracks. It will check the database for new entries every 30 seconds by default. 

```bash
# From the project root directory
.\run_scrobbler.bat
```

### Helper Scripts

These scripts are for development, testing, and data preparation. Because the project is installed as a package, you must run them with the `python -m` flag from the project's root directory.

*   **Build the Local Track Database (Optional)**:
    Generate a local searchable JSON file from your source CSVs. For details on the required CSV format, see `data/README.md`.
    ```bash
    python -m scripts.build_searchable_tracks
    ```
*   **Test a Single Query**:
    Test the entire pipeline with a single song title.
    ```bash
    python -m scripts.test_query "Your Song Title Here"
    ```

## Evaluation and Tuning

This project includes a powerful evaluation suite to fine-tune the track selection algorithm. For more details on the process and how to run the tuning scripts, see the `evaluation/README.md` file.