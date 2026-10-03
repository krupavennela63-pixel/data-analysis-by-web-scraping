# DataScraper Pro

A professional **Web Scraping and Data Analysis** web application built with Python Flask. Extract data from any permitted website, analyze it with Pandas, and visualize with Plotly — all through a beautiful dark-themed dashboard.

---

## Features

- **User Authentication** — Registration, Login, Logout with secure password hashing
- **URL Fetching** — Validates URLs, checks robots.txt, prevents SSRF attacks
- **Element Detection** — Automatically detects HTML tags, IDs, and CSS classes
- **Interactive Selection** — Clickable card UI to select which elements to scrape
- **Multi-page Scraping** — Optional pagination following with configurable max pages
- **Data Cleaning** — Pandas-based deduplication, null handling, whitespace normalization
- **Statistical Analysis** — Mean, median, min, max, std dev, value counts per column
- **Interactive Charts** — Plotly-powered bar charts, pie charts, histograms, line graphs, scatter plots
- **Searchable Data Table** — Paginated table with live search
- **Export** — Download as CSV or Excel (with stats sheet)
- **History** — All scraping sessions stored and accessible
- **Security** — SSRF prevention, robots.txt respect, rate limiting

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python Flask 3.0 |
| Database | SQLite (via SQLAlchemy) |
| Auth | Flask-Login + Werkzeug |
| Scraping | Requests + BeautifulSoup4 + lxml |
| Analysis | Pandas + NumPy |
| Visualization | Plotly.js |
| Frontend | Bootstrap 5 + Vanilla CSS/JS |

---

## Project Structure

```
data analysis project/
├── run.py                    # App entry point
├── requirements.txt          # Python dependencies
├── app/
│   ├── __init__.py           # App factory
│   ├── models.py             # SQLAlchemy models
│   ├── forms.py              # WTForms
│   ├── scraper.py            # Scraping utilities
│   ├── analyzer.py           # Data analysis utilities
│   └── routes/
│       ├── auth.py           # /login /register /logout
│       ├── main.py           # / /dashboard /history
│       ├── scraper.py        # /scrape/* pages
│       └── api.py            # /api/* REST endpoints
├── templates/
│   ├── base.html
│   ├── layout.html           # Sidebar layout
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   ├── main/
│   │   ├── dashboard.html
│   │   └── history.html
│   └── scraper/
│       ├── new_scrape.html
│       ├── select_elements.html
│       └── results.html
├── static/
│   ├── css/main.css
│   └── js/app.js
└── instance/
    └── scraper.db            # SQLite database (auto-created)
```

---

## Setup & Run

### Prerequisites
- Python 3.10+

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the app

```bash
python run.py
```

### 3. Open in browser

```
http://localhost:5000
```

Register an account and start scraping!

---

## Usage Guide

1. **Register/Login** — Create an account on the registration page
2. **Enter URL** — On the dashboard, enter any public website URL (e.g., `https://books.toscrape.com`)
3. **Select Elements** — Choose which HTML elements contain the data you want (CSS classes, tags, IDs)
4. **Configure Options** — Enable multi-page scraping if needed (max 10 pages)
5. **Extract Data** — Click "Extract Selected Data" and wait for results
6. **Analyze & Visualize** — View statistics and interactive Plotly charts
7. **Export** — Download as CSV or Excel

### Recommended Test Sites

These sites are explicitly designed for scraping practice:
- **https://books.toscrape.com** — Book catalog with titles, prices, ratings
- **https://quotes.toscrape.com** — Quotes with authors and tags

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/fetch-page` | Fetch URL, return detected elements |
| POST | `/api/scrape` | Execute scraping with selected selectors |
| GET | `/api/results/<id>` | Get full results + stats + charts |
| GET | `/api/download/<id>/csv` | Download data as CSV |
| GET | `/api/download/<id>/excel` | Download data as Excel |
| DELETE | `/api/session/<id>/delete` | Delete a session |

---

## Security Notes

- **SSRF Protection**: Blocks private IP ranges, localhost, metadata endpoints
- **robots.txt**: Checks and respects robots.txt before scraping
- **Rate Limiting**: 1.5s delay between pages in multi-page mode
- **URL Validation**: Only HTTP/HTTPS schemes allowed, IP addresses blocked
- **Authentication**: All scraping routes require login

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-key-...` | Flask secret key (change in production!) |
