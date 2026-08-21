# Playmogo / DoodStream GitHub Actions Extractor

This repository runs automated batch and on-demand stream extraction using GitHub Actions and authenticated residential proxies.

---

## 📂 Project Structure

- **`.github/workflows/extractor.yml`** — GitHub Actions workflow configuration.
- **`run_extractor.py`** — Batch extractor & single ID resolver script.
- **`app.py`** — FastAPI server (can also be run as a web API if needed).
- **`merged_movie_streaming_data.json`** — JSON database with TMDB/IMDB IDs and Dood/Playmogo mirrors.
- **`requirements.txt`** — Python dependencies (`cloudscraper`, `requests`, `fastapi`, `uvicorn`).

---

## 🚀 How to Run via GitHub Actions

1. Push this folder to your GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/your-username/your-repo.git
   git push -u origin main
   ```

2. Go to the **Actions** tab on GitHub:
   - Select **DoodStream Extractor Action** from the left sidebar.
   - Click **Run workflow**.
   - (Optional) Enter a specific `limit` (e.g. `10`, `50`) or specific `tmdb_or_imdb_id` (e.g. `81` or `tt0087544`).
   - Click the green **Run workflow** button.

3. Results:
   - The workflow extracts the direct stream URLs.
   - Saves them into `extracted_streams.json`.
   - Automatically uploads `extracted_streams.json` as an artifact and commits the file back to your repo.
