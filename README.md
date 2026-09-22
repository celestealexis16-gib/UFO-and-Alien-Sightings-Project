# Signal Atlas: UFO and Alien Sightings Map

Signal Atlas is a Streamlit application for exploring UFO sighting records from the uploaded Excel dataset. It combines an interactive map, filters, charts, report investigation tools, local bookmarks, community notes, and a sighting submission form.

## Requirements

- Windows PowerShell
- Python 3.10 or newer
- The uploaded file `ufo_sighting_data.csv.xlsx`
- A virtual environment in `.venv`

## Setup

Open PowerShell in the project folder:

```powershell
cd "C:\Users\atarranc\Downloads\UFO and Alien Sightings Project"
```

Activate the virtual environment:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

Install the required packages if needed:

```powershell
.\.venv\Scripts\python.exe -m pip install streamlit pandas pydeck openpyxl
```

## Run the app

Use the virtual environment's Python module command:

```powershell
.\.venv\Scripts\python.exe -m streamlit run interactive_map.py
```

If the default port is busy, use another port:

```powershell
.\.venv\Scripts\python.exe -m streamlit run interactive_map.py --server.port 8503
```

Open the URL shown in the terminal, usually:

```text
http://localhost:8501
```

Stop the app with `Ctrl+C` in the terminal.

## App tabs

### Explore the map

Use the map to explore filtered sightings. Hover over a point to see a quick tooltip. Select a report in the investigation section to view its full details.

Available controls include:

- Story modes for famous events and locations
- Date range and timeline playback
- Country and state/province filters
- UFO shape and event type filters
- Encounter duration filter
- Keyword search
- Explained/unexplained assessment filter
- Entity type filter
- Hotspot region filter
- Night sky and daylight map styles
- Heatmap and grid clustering options
- Bookmarked-sightings-only mode

The map section also includes a live shape legend, source links, report comparison, nearby sightings, similar reports, bookmarks, community notes, and JSON export.

### Analytics

Charts respond to the active sidebar filters. Available visualizations include:

- Yearly sighting trend
- Sightings by decade
- Sightings by month
- Sightings by hour
- Sightings by UFO shape
- Top reporting countries
- Top states and provinces
- Seasonal patterns
- Average duration by shape
- Encounter-duration distribution
- Assessment status
- Data completeness confidence
- Common description terms

Use the CSV download button on the map tab to export the currently filtered records.

### Report a sighting

Submit a new sighting using:

- Location
- Latitude and longitude
- Observation date
- Event type
- Description
- Optional contact name or email
- Optional media URL
- Optional image upload

Location and description are required. Descriptions must contain at least 20 characters. Dates cannot be in the future, coordinates cannot be `0, 0`, and media URLs must use `http://` or `https://`.

New reports are stored locally with a `Pending` review status.

### Methodology and data

This tab explains the source dataset and distinguishes spreadsheet values from derived classifications. Status, entity type, confidence, completeness, and duplicate labels are calculated by the application and are not verified conclusions.

## Local files created by the app

The app may create these files or folders in the project directory:

- `sighting_submissions.csv`: submitted user reports
- `favorite_sightings.csv`: bookmarked report IDs
- `sighting_comments.csv`: local community notes
- `submitted_media/`: uploaded report images

These files contain user-generated data. Do not publish them if they contain private contact information.

## Dataset requirements

The application expects the Excel workbook to contain these columns:

- `Date_time`
- `city`
- `state/province`
- `country`
- `UFO_shape`
- `length_of_encounter_seconds`
- `description`
- `date_documented`
- `latitude`
- `longitude`

Records without a valid date, latitude, or longitude are excluded from the map.

## Source links

The spreadsheet does not include an original case URL or case ID. The app therefore creates search links for:

- NUFORC
- MUFON
- Newspaper archives
- Google Maps

These links help locate possible source records but do not prove that a search result is the exact original report.

## Important limitations

- User accounts and researcher verification are not implemented.
- Weather, aircraft paths, satellite paths, launches, and infrastructure overlays require separate datasets or APIs.
- Satellite imagery requires a map provider and access token.
- The app's status and entity classifications are keyword-based heuristics.
- Confidence measures field completeness, not whether a sighting is authentic.
- Local CSV storage is intended for a single-user local project, not production multi-user deployment.

## Troubleshooting

### `streamlit` is not recognized

Run Streamlit through the virtual environment's Python executable:

```powershell
.\.venv\Scripts\python.exe -m streamlit run interactive_map.py
```

### PowerShell blocks activation

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Then activate `.venv` again.

### Excel reader error

Install `openpyxl` into the same environment used to run the app:

```powershell
.\.venv\Scripts\python.exe -m pip install openpyxl
```

### Port already in use

Choose another port:

```powershell
.\.venv\Scripts\python.exe -m streamlit run interactive_map.py --server.port 8503
```

### No records appear

Check the sidebar filters. A narrow date range, story mode, hotspot region, duration range, or favorites-only filter can remove all records.

## Validation

The app can be syntax-checked with:

```powershell
.\.venv\Scripts\python.exe -m py_compile interactive_map.py
```

A Streamlit smoke test can be run with:

```powershell
.\.venv\Scripts\python.exe -c "from streamlit.testing.v1 import AppTest; app=AppTest.from_file('interactive_map.py').run(timeout=180); print(len(app.exception))"
```

A result of `0` means no Streamlit exceptions were reported during the test.
