# Signal Atlas: UFO and Alien Sightings Map

Welcome! Hello, my name is Alexis, and I decided to create this interactive map to bring the world of UFO and alien sightings to life. Driven by a passion for Python and a curiosity about the unexplained, I built The Anomalous Radar to track, visualize, and analyze reported close encounters across the globe.Whether you are looking for historical encounters, mapping out recent midnight anomalies, or searching for hot spots in your own backyard, this project puts the data right at your fingertips. Feel free to filter sightings by date, shape, or region, and see the patterns reveal themselves.Signal Atlas is a Streamlit app for exploring a spreadsheet of reported UFO sightings. It combines an interactive map with filters, timeline exploration, charts, report investigation tools, bookmarks, local community notes, and a form for recording new sightings.

The app is an exploratory research tool. It preserves values from the source spreadsheet and clearly labels classifications calculated by the app as heuristic or completeness-based. It does not verify that a sighting is authentic.
WARNING: THERE MAY BE BUGS DUE TO THE AMOUNT OF DATA ON THIS APP AND THE APP MAY BE LAGGY and SLOW
## Features

- Explore geolocated sightings on an interactive PyDeck map.
- Filter by date, timeline year, country, state or province, shape, event type, duration, keywords, assessment, entity type, region, and bookmarks.
- Use story modes for Roswell, Rendlesham Forest, the Phoenix Lights, the Belgian UFO wave, and Hudson Valley.
- Switch between night and daylight map styles, heatmaps, grid clustering, and famous-location markers.
- Inspect individual records, compare reports, find similar and nearby sightings, and export a selected record as JSON.
- Download the currently filtered records as CSV.
- View analytics for trends, seasons, shapes, locations, durations, assessment labels, and data completeness.
- Submit new sightings with coordinates, descriptions, media URLs, and optional image uploads.
- Save bookmarks and investigation notes locally.

The app limits the map to 6,000 rendered points and sends only map-related fields to the browser. The complete filtered dataset remains available through the CSV download, while cached data loading and export generation keep normal filter interactions responsive.

## Requirements

- Python 3.10 or newer
- Git
- Internet access for map tiles and external search links
- The included `ufo_sighting_data.csv.xlsx` workbook, or another workbook with the required columns listed below

The project does not require a database or external API key for its default map. The Satellite imagery option falls back to the night basemap until a provider and token are configured.

## Quick start

### 1. Clone the repository

```bash
git clone <repository-url>
cd "UFO and Alien Sightings Project"
```

Replace `<repository-url>` with the URL shown by GitHub's **Code** button.

### 2. Create a virtual environment

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If PowerShell blocks activation for the current terminal session, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install streamlit pandas pydeck openpyxl
```

### 4. Start the app

```bash
python -m streamlit run interactive_map.py
```

Streamlit will print a local URL. Open `http://localhost:8501` if it is not opened automatically.

To use a different port:

```bash
python -m streamlit run interactive_map.py --server.port 8503
```

Stop the app with `Ctrl+C` in the terminal.

## Using the app

### Explore the map

Use the sidebar to narrow the dataset. The filters are applied to the map, report selector, nearby-sighting search, and analytics charts.

Hover over a map point for a summary, or choose a record in **Investigate a report** to view its full description and details. From there you can bookmark it, compare it with another report, open external search links, add a local note, and export JSON.

The **Assessment** and **Entity** values are calculated from description keywords. They are not editorial or scientific findings.

### Analytics

The Analytics tab updates with the active filters. It includes yearly and decade trends, month and hour patterns, shapes, countries, states or provinces, seasons, average duration, duration ranges, assessment labels, and common description terms.

Use **Download filtered CSV** on the map tab to export the filtered data, including derived columns created by the app.

### Report a sighting

The report form requires a location and a description of at least 20 characters. It also validates that:

- The observation date is not in the future.
- Latitude and longitude are not both `0, 0`.
- Optional media URLs begin with `http://` or `https://`.
- Uploaded images are PNG or JPEG files.

Submitted reports are saved locally with a `Pending` review status. There is no account system, remote moderation service, or multi-user synchronization.

### Methodology and data

This tab explains the difference between source fields and derived values. Source links are search links because the workbook does not include original case URLs or case IDs. A search result is not proof that the matching original report has been found.

## Dataset format

The app expects `ufo_sighting_data.csv.xlsx` beside `interactive_map.py`. The workbook must contain these columns:

```text
Date_time
city
state/province
country
UFO_shape
length_of_encounter_seconds
description
date_documented
latitude
longitude
```

Column names are trimmed before validation. Rows without a valid date, latitude, or longitude are excluded from the map. Numeric duration, latitude, and longitude values should be stored as numbers or values that pandas can parse.

To use a different workbook, replace the included file while keeping the filename `ufo_sighting_data.csv.xlsx`, or update `DATA_FILE` in `interactive_map.py`.

## Files created at runtime

The app writes these files beside the script when users interact with it:

| File or folder | Purpose |
| --- | --- |
| `sighting_submissions.csv` | Locally submitted sightings and contact details |
| `favorite_sightings.csv` | Bookmarked record IDs |
| `sighting_comments.csv` | Local investigation notes |
| `submitted_media/` | Uploaded report images |

These files may contain personal information. Review them before committing or publishing them to GitHub. For a public repository, add them to `.gitignore` if you do not intend to share local activity.

## Data interpretation and limitations

- `status` is a keyword-based heuristic that may identify terms such as balloon, drone, flare, planet, satellite, aircraft, meteor, or rocket.
- `entity_type` is also keyword-based and is not an identification of a person, creature, or object.
- `confidence_label` measures whether expected fields are populated; it does not measure truth, credibility, or authenticity.
- Possible duplicates are flagged using date, city, shape, and rounded coordinates and require human review.
- The workbook does not include original media, exact case URLs, weather, aircraft paths, satellite paths, launches, or infrastructure overlays.
- The app uses local CSV files rather than a database and is intended for local or single-user use.
- External search links help with research but do not verify a report.

## Troubleshooting

### `streamlit` is not recognized

Run Streamlit through the active environment:

```bash
python -m streamlit run interactive_map.py
```

On Windows, you can also use:

```powershell
.\.venv\Scripts\python.exe -m streamlit run interactive_map.py
```

### PowerShell cannot activate the environment

Run this for the current PowerShell session, then activate `.venv` again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### Excel reader or `openpyxl` error

Install the Excel dependency in the same environment used to run the app:

```bash
python -m pip install openpyxl
```

### Port already in use

Start Streamlit on another port:

```bash
python -m streamlit run interactive_map.py --server.port 8503
```

### No records appear

Check the sidebar. A story mode, narrow date range, timeline year, duration range, keyword search, region, or bookmarks-only filter can remove every record. Also confirm that the workbook is beside `interactive_map.py` and contains the required columns.

### The map is blank or basemap tiles do not load

Confirm that the browser has internet access. The map depends on remote Carto basemap styles and tiles. Satellite imagery is not available without a configured imagery provider.

## Validation

Check Python syntax with:

```bash
python -m py_compile interactive_map.py
```

Run a Streamlit smoke test with:

```bash
python -c "from streamlit.testing.v1 import AppTest; app=AppTest.from_file('interactive_map.py').run(timeout=180); print(len(app.exception))"
```

The smoke test should print `0` when no Streamlit exceptions are reported.

## Project structure

```text
.
├── interactive_map.py
├── ufo_sighting_data.csv.xlsx
└── README.md
```

Runtime files listed above may appear after using the app.

