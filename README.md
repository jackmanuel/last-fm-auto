# Discord Last.fm Scrobbler

This project automatically scrobbles songs played by a Discord music bot to a designated Last.fm account. It works by monitoring the bot's playback activity and using the Last.fm API to log the tracks.

## How It Works

1.  **Monitors Discord:** A component (not included in this script) must monitor a Discord guild for songs played by a music bot.
2.  **Logs Plays:** This listening component logs song information into a shared SQLite database.
3.  **Scrobbles to Last.fm:** The `scrobbler.py` script reads new, unprocessed songs from the database, cleans up the titles, and uses the Last.fm API to scrobble them to the specified account.

## Setup

1.  **Prerequisites:**
    *   Python 3
    *   A Last.fm API key and secret
    *   A Discord bot or other method for tracking song plays.

2.  **Configuration:**
    *   Clone this repository.
    *   Install dependencies: `pip install -r requirements.txt`
    *   Create a `.env` file in the root directory with the following:
        ```
        LAST_FM_API_KEY="your_last_fm_api_key"
        LAST_FM_SHARED_SECRET="your_last_fm_api_secret"
        LAST_FM_SESSION_KEY="you_last_fm_session_key"
        DATABASE_PATH="/path/to/your/database.db"
        GUILD_ID="your_discord_guild_id"
        ```

3.  **Database:**
    *   Ensure the SQLite database specified in `DATABASE_PATH` exists and contains a `play_history` table. A setup script may be required if one does not exist.

4.  **Run the Scrobbler:**
    *   If on windows, there is a batch script: `./run_scrobbler.bat`
    *   You can also start the bot with python directly: `python scrobbler.py`