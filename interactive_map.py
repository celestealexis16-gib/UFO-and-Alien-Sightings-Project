from pathlib import Path
from datetime import datetime
import html
import json
import re
from urllib.parse import quote_plus, urlparse

import pandas as pd
import pydeck as pdk
import streamlit as st


DATA_FILE = Path(__file__).with_name("ufo_sighting_data.csv.xlsx")
SUBMISSIONS_FILE = Path(__file__).with_name("sighting_submissions.csv")
FAVORITES_FILE = Path(__file__).with_name("favorite_sightings.csv")
COMMENTS_FILE = Path(__file__).with_name("sighting_comments.csv")
MEDIA_DIR = Path(__file__).with_name("submitted_media")
REQUIRED_COLUMNS = {"Date_time", "city", "state/province", "country", "UFO_shape", "length_of_encounter_seconds", "description", "date_documented", "latitude", "longitude"}
MAP_POINT_LIMIT = 6000

SHAPE_COLORS = {
	"light": [255, 204, 92],
	"circle": [67, 211, 191],
	"disk": [91, 141, 239],
	"triangle": [245, 119, 160],
	"sphere": [161, 124, 255],
	"fireball": [255, 133, 82],
	"formation": [86, 191, 255],
	"unknown": [180, 190, 202],
}

STORY_MODES = {
	"All sightings": {"center": [20, 0], "zoom": 1.4, "year": None, "note": "Explore the complete dataset."},
	"Roswell | 1947": {"center": [33.39, -104.52], "zoom": 6, "year": 1947, "note": "A guided anchor for the 1947 New Mexico story."},
	"Rendlesham Forest | 1980": {"center": [52.12, 1.45], "zoom": 8, "year": 1980, "note": "A guided anchor for the December 1980 Suffolk reports."},
	"Phoenix Lights | 1997": {"center": [33.45, -112.07], "zoom": 7, "year": 1997, "note": "A guided anchor for the March 1997 Arizona reports."},
	"Belgian UFO wave | 1989": {"center": [50.85, 4.35], "zoom": 6, "year": 1989, "note": "A guided anchor for the late-1980s Belgium reports."},
	"Hudson Valley | 1983": {"center": [41.50, -73.97], "zoom": 7, "year": 1983, "note": "A guided anchor for the 1983 Hudson Valley reports."},
}

STORY_POINTS = pd.DataFrame(
	[
		{"name": "Roswell", "latitude": 33.3943, "longitude": -104.5230, "story": "1947"},
		{"name": "Rendlesham Forest", "latitude": 52.12, "longitude": 1.45, "story": "1980"},
		{"name": "Phoenix Lights", "latitude": 33.4484, "longitude": -112.0740, "story": "1997"},
		{"name": "Area 51", "latitude": 37.2350, "longitude": -115.8111, "story": "reference"},
		{"name": "Bonnybridge", "latitude": 56.0000, "longitude": -3.8833, "story": "reference"},
	]
)


@st.cache_data
def load_data() -> pd.DataFrame:
	data = pd.read_excel(DATA_FILE)
	data.columns = [str(column).strip() for column in data.columns]
	missing_columns = REQUIRED_COLUMNS - set(data.columns)
	if missing_columns:
		raise ValueError(f"The spreadsheet is missing required columns: {', '.join(sorted(missing_columns))}")
	data["Date_time"] = pd.to_datetime(data["Date_time"], errors="coerce")
	data["latitude"] = pd.to_numeric(data["latitude"], errors="coerce")
	data["longitude"] = pd.to_numeric(data["longitude"], errors="coerce")
	data["length_of_encounter_seconds"] = pd.to_numeric(data["length_of_encounter_seconds"], errors="coerce")
	data = data.dropna(subset=["Date_time", "latitude", "longitude"]).copy()
	data["description"] = data["description"].fillna("").astype(str)
	data["shape"] = data["UFO_shape"].fillna("unknown").astype(str).str.strip().str.lower()
	data["event_type"] = data["shape"].map(lambda shape: shape.title())
	data["country_label"] = data["country"].fillna("unknown").astype(str).str.upper()
	data["year"] = data["Date_time"].dt.year
	data["decade"] = (data["year"] // 10 * 10).astype(int)
	data["month"] = data["Date_time"].dt.month
	data["season"] = data["month"].map({12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring", 6: "Summer", 7: "Summer", 8: "Summer", 9: "Autumn", 10: "Autumn", 11: "Autumn"})
	data["state_label"] = data["state/province"].fillna("unknown").astype(str).str.upper()
	data["date_label"] = data["Date_time"].dt.strftime("%d %b %Y, %H:%M")
	data["record_id"] = data.index.astype(str)
	data["status"] = data["description"].fillna("").map(infer_status)
	data["entity_type"] = data["description"].fillna("").map(infer_entity)
	data["completeness_score"] = data.apply(calculate_completeness, axis=1)
	data["confidence_label"] = data["completeness_score"].map(lambda score: "High" if score >= 80 else "Medium" if score >= 50 else "Low")
	data["duplicate_key"] = data.apply(lambda row: f"{row['Date_time'].date()}|{row['city']}|{row['shape']}|{round(row['latitude'], 2)}|{round(row['longitude'], 2)}", axis=1)
	data["possible_duplicate"] = data.duplicated("duplicate_key", keep=False)
	data["color"] = data["shape"].map(lambda shape: SHAPE_COLORS.get(shape, [180, 190, 202]))
	data["source_url"] = data.apply(build_source_url, axis=1)
	return data


@st.cache_data(max_entries=32)
def serialize_csv(data: pd.DataFrame) -> bytes:
	return data.to_csv(index=False).encode("utf-8")


def infer_status(description: str) -> str:
	explained_terms = r"balloon|drone|flare|planet|venus|satellite|aircraft|meteor|rocket"
	if re.search(explained_terms, description.lower()):
		return "Identified / explained (heuristic)"
	return "Unexplained / unverified"


def infer_entity(description: str) -> str:
	description = description.lower()
	for entity, terms in {
		"Greys": ["grey", "gray", "big headed"],
		"Reptilians": ["reptilian", "lizard"],
		"Nordics / Tall Whites": ["nordic", "tall white"],
		"Biomorphic": ["biomorphic", "organic creature"],
	}.items():
		if any(term in description for term in terms):
			return entity
	return "Unclassified"


def calculate_completeness(record: pd.Series) -> int:
	fields = ["Date_time", "city", "country", "UFO_shape", "description", "latitude", "longitude", "length_of_encounter_seconds", "date_documented"]
	return round(sum(pd.notna(record.get(field)) and str(record.get(field)).strip() != "" for field in fields) / len(fields) * 100)


def build_source_url(record: pd.Series) -> str:
	query = " ".join(
		str(value)
		for value in [record["Date_time"].date(), record["city"], record["country"], record["UFO_shape"]]
		if pd.notna(value)
	)
	return f"https://www.google.com/search?q={quote_plus(f'site:nuforc.org {query}')}"


def format_duration(seconds) -> str:
	if pd.isna(seconds):
		return "Not supplied"
	seconds = int(seconds)
	if seconds < 60:
		return f"{seconds} seconds"
	return f"{seconds // 60} minutes"


def map_links(record: pd.Series) -> dict[str, str]:
	place = f"{record['latitude']},{record['longitude']}"
	query = quote_plus(f"{record['city']} {record['country_label']} UFO {record['year']}")
	return {
		"Google Maps": f"https://www.google.com/maps/search/?api=1&query={place}",
		"NUFORC search": record["source_url"],
		"MUFON search": f"https://www.google.com/search?q=site%3Amufon.com+{query}",
		"Newspaper archive search": f"https://www.google.com/search?q={query}+newspaper+archive",
	}


def make_tooltip() -> dict:
	return {
		"html": "<b>{shape}</b> · {date_label}<br/>{city}, {country_label}<br/><br/>{description}",
		"style": {"backgroundColor": "#101820", "color": "#f4f7f8", "fontSize": "12px"},
	}


def summarize_description(description: str) -> str:
	text = str(description).strip()
	if not text:
		return "No description was supplied."
	sentences = re.split(r"(?<=[.!?])\s+", text)
	return " ".join(sentences[:2])[:420]


def save_row(path: Path, row: dict) -> None:
	frame = pd.DataFrame([row])
	if path.exists():
		frame.to_csv(path, mode="a", header=False, index=False)
	else:
		frame.to_csv(path, index=False)


def load_ids(path: Path) -> set[str]:
	if not path.exists():
		return set()
	try:
		return set(pd.read_csv(path)["record_id"].astype(str))
	except (OSError, KeyError, pd.errors.ParserError):
		return set()


def remove_id(path: Path, record_id: str) -> bool:
	if not path.exists():
		return True
	try:
		frame = pd.read_csv(path)
		if "record_id" not in frame.columns:
			return False
		frame = frame[frame["record_id"].astype(str) != str(record_id)]
		frame.to_csv(path, index=False)
		return True
	except (OSError, pd.errors.ParserError):
		return False


def selected_record_id(map_event) -> str | None:
	if not map_event:
		return None
	try:
		selection = map_event.selection
		objects = selection.objects
		if isinstance(objects, dict):
			objects = objects.get("sightings", [])
		if objects:
			return str(objects[0].get("record_id"))
	except (AttributeError, IndexError, KeyError, TypeError):
		return None
	return None


def save_submission(submission: dict) -> bool:
	new_submission = pd.DataFrame([submission])
	try:
		if SUBMISSIONS_FILE.exists():
			new_submission.to_csv(SUBMISSIONS_FILE, mode="a", header=False, index=False)
		else:
			new_submission.to_csv(SUBMISSIONS_FILE, index=False)
		return True
	except OSError:
		return False


def advance_timeline(min_year: int, max_year: int) -> None:
	current_year = st.session_state.get("playback_year", max_year)
	st.session_state["playback_year"] = min_year if current_year >= max_year else current_year + 1


def valid_url(value: str) -> bool:
	if not value:
		return True
	parsed = urlparse(value)
	return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def main() -> None:
	st.set_page_config(page_title="Signal Atlas | UFO & Alien Sightings", page_icon="🛸", layout="wide", initial_sidebar_state="expanded")
	st.markdown(
		"""
		<style>
		@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
		:root { --ink:#ffffff; --muted:#e4e9ff; --panel:rgba(16, 20, 43, .82); --accent:#8ffff0; --pink:#ff9bd0; }
		.stApp { background: radial-gradient(ellipse at 12% 0%, rgba(77, 54, 143, .44), transparent 37%), radial-gradient(ellipse at 92% 18%, rgba(19, 130, 146, .25), transparent 32%), linear-gradient(135deg, #070b1e 0%, #111033 50%, #090b1c 100%); color:var(--ink); overflow:hidden; }
		.stApp::before { content:''; position:fixed; inset:0; pointer-events:none; opacity:.58; background-image:radial-gradient(2px 2px at 12% 22%, #fff, transparent),radial-gradient(1px 1px at 27% 75%, #fff, transparent),radial-gradient(2px 2px at 73% 13%, #fff, transparent),radial-gradient(1px 1px at 86% 69%, #fff, transparent),radial-gradient(1px 1px at 58% 84%, #fff, transparent),radial-gradient(2px 2px at 44% 34%, #fff, transparent); animation:drift 18s linear infinite; }
		.stApp::after { content:''; position:fixed; width:70vw; height:35vw; right:-18vw; top:8vh; pointer-events:none; opacity:.23; border:1px solid #f47ebd; border-radius:50%; transform:rotate(-24deg); box-shadow:0 0 60px rgba(244,126,189,.5), inset 0 0 50px rgba(103,225,208,.25); }
		@keyframes drift { from { transform:translateY(0); } 50% { transform:translateY(8px); } to { transform:translateY(0); } }
		h1,h2,h3,p,div,span,label { font-family:'Space Grotesk', sans-serif; color:var(--ink); }
		code,.mono { font-family:'DM Mono', monospace; }
		.stApp, .stApp p, .stApp label, [data-testid='stSidebar'], [data-testid='stSidebar'] p, [data-testid='stSidebar'] label { color:var(--ink); }
		.stCaption, [data-testid='stCaptionContainer'], [data-testid='stCaptionContainer'] p, .stMarkdown .subtle { color:var(--muted) !important; }
		[data-testid='stWidgetLabel'] p, [data-testid='stWidgetLabel'] label { color:#ffffff !important; font-weight:600; }
		input, textarea { color:#ffffff !important; background-color:#171d42 !important; caret-color:#8ffff0 !important; }
		input::placeholder, textarea::placeholder { color:#d7dcf5 !important; opacity:1 !important; }
		[data-baseweb='select'] > div { background-color:#171d42 !important; border-color:#8ffff0 !important; color:#ffffff !important; }
		[data-baseweb='select'] [data-testid='stMarkdownContainer'], [data-baseweb='select'] div, [data-baseweb='select'] span { color:#ffffff !important; }
		[data-baseweb='popover'], [role='listbox'], [role='option'] { background-color:#171d42 !important; color:#ffffff !important; }
		[role='option']:hover, [aria-selected='true'] { background-color:#354078 !important; color:#ffffff !important; }
		.stButton button, .stFormSubmitButton button, .stDownloadButton button { background-color:#183b54 !important; color:#ffffff !important; font-weight:700 !important; }
		.stButton button p, .stFormSubmitButton button p, .stDownloadButton button p { color:#ffffff !important; }
		[data-testid='stCaptionContainer'] p { color:#e4e9ff !important; }
		[data-testid='stMetricValue'] { font-family:'DM Mono', monospace; color:var(--accent); text-shadow:0 0 18px rgba(103,225,208,.45); }
		[data-testid='stSidebar'] { background:rgba(7, 10, 28, .86); border-right:1px solid rgba(103,225,208,.24); }
		[data-testid='stSidebar'] > div:first-child { background:linear-gradient(180deg, rgba(23, 29, 63, .64), rgba(7, 10, 28, .35)); }
		[data-testid='stMetric'], [data-testid='stExpander'], .stPlotlyChart, [data-testid='stDataFrame'] { border:1px solid rgba(103,225,208,.2); border-radius:14px; background:var(--panel); box-shadow:0 0 28px rgba(42, 35, 107, .2), inset 0 1px rgba(255,255,255,.05); }
		[data-testid='stMetric'] { padding:12px; }
		.stButton button, .stDownloadButton button { border:1px solid rgba(103,225,208,.5); box-shadow:0 0 14px rgba(103,225,208,.12); transition:all .2s ease; }
		.stButton button:hover, .stDownloadButton button:hover { border-color:var(--pink); box-shadow:0 0 18px rgba(244,126,189,.35); transform:translateY(-1px); }
		.eyebrow { color:var(--accent); font:500 11px 'DM Mono'; letter-spacing:2px; text-transform:uppercase; }
		.subtle { color:var(--muted) !important; font-size:14px; }
		.hero { padding:20px 24px 18px; border:1px solid rgba(244,126,189,.24); border-radius:18px; background:linear-gradient(120deg, rgba(16,20,58,.78), rgba(21,44,67,.35)); box-shadow:0 0 40px rgba(100,52,162,.2); }
		.hero h1 { margin:4px 0 4px; font-size:clamp(2rem, 5vw, 4rem); letter-spacing:-1px; }
		.hero .signal { color:var(--pink); text-shadow:0 0 18px rgba(244,126,189,.45); }
		.nearby-table { overflow:hidden; border:1px solid rgba(143,255,240,.34); border-radius:16px; background:rgba(12,18,46,.88); box-shadow:0 0 26px rgba(103,225,208,.12), inset 0 1px rgba(255,255,255,.08); }
		.nearby-table table { width:100%; border-collapse:collapse; table-layout:fixed; }
		.nearby-table th { padding:12px 14px; color:#8ffff0; background:linear-gradient(90deg, rgba(31,58,91,.95), rgba(70,37,92,.82)); font:500 11px 'DM Mono'; letter-spacing:1px; text-align:left; text-transform:uppercase; }
		.nearby-table td { padding:12px 14px; border-top:1px solid rgba(228,233,255,.12); color:#ffffff; font-size:13px; vertical-align:top; }
		.nearby-table tr:nth-child(even) td { background:rgba(33,43,83,.34); }
		.nearby-table tr:hover td { background:rgba(244,126,189,.14); }
		.nearby-table th:nth-child(1), .nearby-table td:nth-child(1) { width:18%; }
		.nearby-table th:nth-child(2), .nearby-table td:nth-child(2) { width:17%; }
		.nearby-table th:nth-child(3), .nearby-table td:nth-child(3) { width:12%; }
		.nearby-table th:nth-child(4), .nearby-table td:nth-child(4) { width:14%; }
		.nearby-table th:nth-child(5), .nearby-table td:nth-child(5) { width:39%; }
		.shape-badge { display:inline-block; padding:4px 8px; border:1px solid rgba(143,255,240,.48); border-radius:999px; color:#8ffff0; background:rgba(103,225,208,.12); font:500 11px 'DM Mono'; }
		@media (max-width: 700px) { .hero { padding:16px; } .hero h1 { font-size:2.1rem; } [data-testid='stMetricValue'] { font-size:1.2rem; } }
		</style>
		""",
		unsafe_allow_html=True,
	)

	try:
		data = load_data()
	except (FileNotFoundError, ImportError, ValueError, OSError) as error:
		st.error(f"Unable to load the sightings spreadsheet: {error}")
		st.stop()
	min_date = data["Date_time"].min().date()
	max_date = data["Date_time"].max().date()

	with st.sidebar:
		st.markdown("<div class='eyebrow'>👽 Global anomaly archive 🛸</div>", unsafe_allow_html=True)
		st.title("🛸 Signal Atlas")
		st.caption("A visual index of reported aerial phenomena. Dataset fields are preserved; derived classifications are labeled.")
		light_mode = st.toggle("Light theme", value=False)
		if light_mode:
			st.markdown("<style>.stApp{background:linear-gradient(135deg,#f6f8ff,#e8f4f4)!important;color:#11152b!important}.stApp h1,.stApp h2,.stApp h3,.stApp p,.stApp label,.stApp span{color:#11152b!important}[data-testid='stSidebar']{background:#e7ecfb!important}[data-baseweb='select']>div,input,textarea{background:#ffffff!important;color:#11152b!important}</style>", unsafe_allow_html=True)
		st.markdown("[Open NUFORC archive](https://nuforc.org/)")
		st.divider()
		story_name = st.selectbox("Story mode", list(STORY_MODES))
		story = STORY_MODES[story_name]
		st.markdown(f"<span class='subtle'>{story['note']}</span>", unsafe_allow_html=True)
		st.divider()
		date_range = st.slider("Reported between", min_date, max_date, (min_date, max_date), format="YYYY")
		if "playback_year" not in st.session_state:
			st.session_state["playback_year"] = max_date.year
		playback_year = st.slider("Timeline playback year", min_date.year, max_date.year, key="playback_year", format="%d")
		st.button("Advance timeline", icon=":material/skip_next:", on_click=advance_timeline, args=(min_date.year, max_date.year))
		shapes = sorted(data["shape"].unique())
		selected_shapes = st.multiselect("Reported shape", shapes, default=shapes)
		countries = sorted(data["country_label"].unique())
		selected_countries = st.multiselect("Country", countries, default=countries)
		states = sorted(data["state_label"].unique())
		selected_states = st.multiselect("State / province", states, default=states)
		event_types = sorted(data["event_type"].unique())
		selected_event_types = st.multiselect("Event type", event_types, default=event_types)
		statuses = sorted(data["status"].unique())
		selected_statuses = st.multiselect("Assessment status", statuses, default=statuses)
		entities = sorted(data["entity_type"].unique())
		selected_entities = st.multiselect("Entity type", entities, default=entities)
		status_view = st.segmented_control("Assessment", ["All", "Unexplained", "Identified"], default="All")
		search = st.text_input("Keywords", placeholder="military, lights, triangle")
		max_duration = int(data["length_of_encounter_seconds"].max())
		duration_range = st.slider("Encounter duration (seconds)", 0, max_duration, (0, max_duration))
		st.divider()
		show_heatmap = st.checkbox("Heatmap hotspots", value=True)
		show_story_points = st.checkbox("Famous locations", value=True)
		show_cluster_hint = st.checkbox("Cluster points", value=True)
		show_favorites = st.checkbox("Only bookmarked sightings", value=False)
		map_theme = st.selectbox("Map atmosphere", ["Night sky", "Daylight", "Satellite imagery"])
		hotspot_region = st.selectbox("Hotspot region", ["All regions", "United States", "United Kingdom", "Australia", "Canada", "Europe"])

	filtered = data[
		data["Date_time"].dt.date.between(date_range[0], date_range[1])
		& (data["year"] <= playback_year)
		& data["shape"].isin(selected_shapes)
		& data["country_label"].isin(selected_countries)
		& data["state_label"].isin(selected_states)
		& data["event_type"].isin(selected_event_types)
		& data["status"].isin(selected_statuses)
		& data["entity_type"].isin(selected_entities)
		& data["length_of_encounter_seconds"].notna()
		& data["length_of_encounter_seconds"].between(duration_range[0], duration_range[1])
	].copy()
	if status_view == "Unexplained":
		filtered = filtered[filtered["status"].str.startswith("Unexplained")]
	elif status_view == "Identified":
		filtered = filtered[filtered["status"].str.startswith("Identified")]
	if search:
		filtered = filtered[filtered["description"].fillna("").str.contains(search, case=False, na=False, regex=False)]
	if story["year"] is not None:
		filtered = filtered[filtered["year"].eq(story["year"])]
	favorite_ids = load_ids(FAVORITES_FILE)
	if show_favorites:
		filtered = filtered[filtered["record_id"].isin(favorite_ids)]
	if hotspot_region != "All regions":
		region_countries = {"United States": ["US"], "United Kingdom": ["GB"], "Australia": ["AU"], "Canada": ["CA"], "Europe": ["AT", "BE", "CH", "DE", "DK", "ES", "FI", "FR", "IE", "IT", "NL", "NO", "PT", "SE"]}
		filtered = filtered[filtered["country_label"].isin(region_countries[hotspot_region])]

	map_tab, analytics_tab, report_tab, methodology_tab = st.tabs(["🛸 Explore the map", "📊 Analytics", "👽 Report a sighting", "Methodology & data"])
	with map_tab:
		with st.expander("How to read this page", expanded=False):
			st.write("Use the sidebar filters to narrow the sightings. Hover over map points for quick details, then use Investigate a report to search and inspect one record. The nearby table shows the closest reports from the same year.")
	with report_tab:
		with st.expander("How to read this page", expanded=False):
			st.write("Enter the location and description of a sighting. Coordinates help place it on a future map layer. You can attach an image or media URL. New submissions are saved locally and marked Pending review.")
		st.subheader("👽 Transmit a new sighting 🛸")
		st.caption("Submissions are stored locally in sighting_submissions.csv and marked Pending review.")
		with st.form("report_sighting", clear_on_submit=True):
			report_cols = st.columns(2)
			with report_cols[0]:
				reporter = st.text_input("Name or contact email (optional)")
				location = st.text_input("Location", placeholder="City, country")
				latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=0.0, format="%.5f")
				longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=0.0, format="%.5f")
			with report_cols[1]:
				report_date = st.date_input("Date observed", value=datetime.now().date())
				event_type = st.selectbox("Event type", ["Light", "Circle", "Disk", "Triangle", "Sphere", "Formation", "Other"])
				media_url = st.text_input("Image or video URL (optional)", placeholder="https://...")
				uploaded_image = st.file_uploader("Image evidence (optional)", type=["png", "jpg", "jpeg"])
			description = st.text_area("What did you observe?", height=120)
			submitted = st.form_submit_button("Transmit report", icon=":material/send:")
			if submitted:
				validation_errors = []
				if not location.strip() or len(description.strip()) < 20:
					validation_errors.append("Location and a description of at least 20 characters are required.")
				if report_date > datetime.now().date():
					validation_errors.append("The observation date cannot be in the future.")
				if latitude == 0 and longitude == 0:
					validation_errors.append("Please provide coordinates other than 0, 0.")
				if not valid_url(media_url):
					validation_errors.append("The media URL must start with http:// or https://.")
				if validation_errors:
					st.error(" ".join(validation_errors))
				else:
					image_name = ""
					if uploaded_image:
						MEDIA_DIR.mkdir(exist_ok=True)
						image_name = re.sub(r"[^A-Za-z0-9_.-]", "_", uploaded_image.name)
						(MEDIA_DIR / image_name).write_bytes(uploaded_image.getvalue())
					saved = save_submission({"submitted_at": datetime.now().isoformat(timespec="seconds"), "reporter_or_email": reporter, "location": location.strip(), "latitude": latitude, "longitude": longitude, "observed_date": report_date.isoformat(), "event_type": event_type, "description": description.strip(), "media_url": media_url.strip(), "image_name": image_name, "review_status": "Pending"})
					st.success("Report transmitted. Review status: Pending.") if saved else st.error("The report could not be saved locally.")
	with methodology_tab:
		with st.expander("How to read this page", expanded=False):
			st.write("This page explains which values come directly from the spreadsheet and which labels are heuristic. Source links are search links because the uploaded file does not include original case URLs.")
		st.subheader("About this archive")
		st.write("The map uses the uploaded UFO sighting spreadsheet. Date, location, shape, duration, and description are dataset facts. Assessment status and entity type are heuristic labels derived from description keywords and are not verified conclusions.")
		st.write("The spreadsheet does not include original media, exact case URLs, infrastructure overlays, or review outcomes. Source links are searches designed to help locate corresponding NUFORC, MUFON, and newspaper records.")
		st.info("Infrastructure layers such as airports, military bases, flight paths, dark-sky areas, and launches require separate geospatial datasets before they can be shown accurately.")

	with map_tab:
		st.markdown("<section class='hero'><div class='eyebrow'>🛸 UFO / 👽 ALIEN SIGHTINGS · LIVE ARCHIVE</div><h1>The sky leaves a <span class='signal'>paper trail.</span></h1><p class='subtle'>Navigate the dark between knowns. Search reports by geography, event type, era, and the stories attached to them.</p></section>", unsafe_allow_html=True)
		metric_cols = st.columns(4)
		metric_cols[0].metric("Visible reports", f"{len(filtered):,}")
		metric_cols[1].metric("Countries", f"{filtered['country_label'].nunique():,}")
		metric_cols[2].metric("Peak year", str(int(filtered["year"].value_counts().idxmax())) if not filtered.empty else "—")
		metric_cols[3].metric("Shape families", f"{filtered['shape'].nunique():,}")
		export_data = filtered.drop(columns=["color"])
		st.download_button("Download filtered CSV", serialize_csv(export_data), "filtered_sightings.csv", "text/csv", icon=":material/download:")

	if filtered.empty:
		st.warning("No records match the current filters.")
		return

	# Keep the full filtered frame for exports and details, but send only map fields to the browser.
	map_columns = ["record_id", "shape", "date_label", "city", "country_label", "description", "latitude", "longitude", "color"]
	map_data = filtered.loc[:, map_columns]
	if len(map_data) > MAP_POINT_LIMIT:
		map_data = map_data.sample(MAP_POINT_LIMIT, random_state=42)
	with map_tab:
		map_layers = []
		map_style = {
			"Night sky": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
			"Daylight": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
			"Satellite imagery": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
		}[map_theme]
		if show_heatmap:
			map_layers.append(pdk.Layer("HeatmapLayer", map_data, get_position="[longitude, latitude]", radius_pixels=35, intensity=1, threshold=0.05))
		if show_cluster_hint:
			map_layers.append(pdk.Layer("GridLayer", map_data, id="sighting-clusters", pickable=False, cell_size=45000, elevation_scale=40, extruded=True, get_position="[longitude, latitude]"))
		scatter_radius = 1700 if show_cluster_hint else 850
		map_layers.append(
			pdk.Layer(
				"ScatterplotLayer", map_data, id="sightings", pickable=True, opacity=0.78, stroked=True, filled=True,
				radius_min_pixels=2, radius_max_pixels=12, get_position="[longitude, latitude]",
				get_radius=scatter_radius, get_fill_color="color", get_line_color=[238, 246, 247], line_width_min_pixels=0.5,
			)
		)
		if show_story_points:
			map_layers.append(
				pdk.Layer("ScatterplotLayer", STORY_POINTS, pickable=True, get_position="[longitude, latitude]",
						  get_radius=8000, radius_min_pixels=5, radius_max_pixels=11, get_fill_color=[255, 255, 255],
						  get_line_color=[103, 211, 193], line_width_min_pixels=2)
			)
		view = pdk.ViewState(latitude=story["center"][0], longitude=story["center"][1], zoom=story["zoom"], min_zoom=1, max_zoom=15)
		map_event = st.pydeck_chart(
			pdk.Deck(map_style=map_style, initial_view_state=view,
					 layers=map_layers, tooltip=make_tooltip()), width="stretch", height=610,
			on_select="rerun", selection_mode="single-object", key="sighting_map"
		)
		if map_theme == "Satellite imagery":
			st.info("Satellite imagery requires a provider token. The map keeps the night base layer until one is configured.")
		legend_html = " ".join(f"<span class='shape-badge' style='border-color:rgb({color[0]},{color[1]},{color[2]});color:rgb({color[0]},{color[1]},{color[2]})'>{html.escape(shape.title())}</span>" for shape, color in SHAPE_COLORS.items() if shape in filtered["shape"].unique())
		st.markdown(f"**Live legend** · {legend_html}", unsafe_allow_html=True)
		st.caption("Country borders come from the basemap. Aircraft, satellite paths, weather, and launch overlays require separate data sources.")

	with analytics_tab:
		with st.expander("How to read this page", expanded=False):
			st.write("All charts respond to the sidebar filters. The trend line counts reports by year; bar charts compare shapes, countries, states, months, hours, durations, and assessment labels. These patterns describe the dataset and do not prove cause or authenticity.")
		st.subheader("Sightings analytics")
		timeline = filtered.groupby("year", as_index=False).size().rename(columns={"size": "reports"})
		decade_counts = filtered.groupby("decade").size().rename("reports")
		st.caption("Yearly trend")
		st.line_chart(timeline.set_index("year"), height=180, color="#67d3c1")
		graph_cols = st.columns(3)
		with graph_cols[0]:
			st.caption("Sightings by decade")
			st.bar_chart(decade_counts, height=210, color="#67d3c1")
		with graph_cols[1]:
			st.caption("Reports by month")
			month_counts = filtered["Date_time"].dt.month.value_counts().sort_index()
			month_counts.index = [datetime(2000, month, 1).strftime("%b") for month in month_counts.index]
			st.bar_chart(month_counts, height=210, color="#8ffff0")
		with graph_cols[2]:
			st.caption("Reports by hour of day")
			hour_counts = filtered["Date_time"].dt.hour.value_counts().sort_index()
			st.bar_chart(hour_counts, height=210, color="#ff9bd0")

		chart_cols = st.columns(3)
		with chart_cols[0]:
			st.caption("Sightings by shape")
			st.bar_chart(filtered["shape"].value_counts().head(10), height=190, color="#ff9bd0")
		with chart_cols[1]:
			st.caption("Top reporting countries")
			st.bar_chart(filtered["country_label"].value_counts(), height=190, color="#8ffff0")
		with chart_cols[2]:
			st.caption("Top states / provinces")
			st.bar_chart(filtered["state_label"].replace("UNKNOWN", pd.NA).dropna().value_counts().head(10), height=190, color="#67e1d0")
		st.caption("Seasonal pattern")
		st.bar_chart(filtered["season"].value_counts().reindex(["Winter", "Spring", "Summer", "Autumn"]).fillna(0), height=190, color="#f47ebd")
		st.caption("Average duration by shape")
		st.bar_chart(filtered.groupby("shape")["length_of_encounter_seconds"].mean().sort_values(ascending=False).head(10), height=190, color="#8ffff0")
		st.caption("Data completeness")
		st.bar_chart(filtered["confidence_label"].value_counts().reindex(["High", "Medium", "Low"]).fillna(0), height=190, color="#a98cff")

		more_chart_cols = st.columns(3)
		with more_chart_cols[0]:
			st.caption("Encounter duration distribution")
			duration_bins = pd.cut(filtered["length_of_encounter_seconds"], bins=[-1, 10, 60, 300, 3600, float("inf")], labels=["0–10s", "11–60s", "1–5m", "5–60m", "60m+"]).value_counts().sort_index()
			st.bar_chart(duration_bins, height=190, color="#a98cff")
		with more_chart_cols[1]:
			st.caption("Assessment status")
			st.bar_chart(filtered["status"].str.replace(" (heuristic)", "", regex=False).value_counts(), height=190, color="#ff9bd0")
		with more_chart_cols[2]:
			st.caption("Most frequent terms")
			words = filtered["description"].str.lower().str.findall(r"[a-z]{5,}").explode().value_counts().head(8)
			st.dataframe(words.rename("mentions"), width="stretch", height=190)

	with map_tab:
		st.subheader("Investigate a report")
		filtered_by_id = filtered.set_index("record_id")
		report_search = st.text_input(
			"Search this report list",
			placeholder="Search city, country, shape, date, or description...",
			key="report_search",
		)
	if report_search:
		search_text = report_search.lower()
		searchable = filtered_by_id[["city", "country_label", "shape", "date_label", "description"]].fillna("").astype(str).agg(" ".join, axis=1)
		matching_ids = searchable[searchable.str.contains(search_text, case=False, na=False, regex=False)].index.tolist()
	else:
		matching_ids = filtered_by_id.index.tolist()

	with map_tab:
		options = matching_ids
		if not options:
			st.info("No reports match this search.")
			return
		clicked_id = selected_record_id(map_event)
		default_index = options.index(clicked_id) if clicked_id in options else 0
		selected_id = st.selectbox("Select a point from the filtered archive", options, index=default_index, format_func=lambda value: f"{filtered_by_id.loc[value, 'date_label']} · {filtered_by_id.loc[value, 'city']} · {filtered_by_id.loc[value, 'shape']}")
		record = filtered_by_id.loc[selected_id]
		comparison_options = [item for item in options if item != selected_id]
		if comparison_options:
			comparison_id = st.selectbox("Compare with another report", comparison_options, format_func=lambda value: f"{filtered_by_id.loc[value, 'date_label']} · {filtered_by_id.loc[value, 'city']} · {filtered_by_id.loc[value, 'shape']}")
			comparison_record = filtered_by_id.loc[comparison_id]
			compare_left, compare_right = st.columns(2)
			with compare_left:
				st.markdown(f"**Primary · {str(record['city']).title()}**")
				st.write(f"{record['date_label']} · {record['shape'].title()} · {format_duration(record['length_of_encounter_seconds'])}")
			with compare_right:
				st.markdown(f"**Comparison · {str(comparison_record['city']).title()}**")
				st.write(f"{comparison_record['date_label']} · {comparison_record['shape'].title()} · {format_duration(comparison_record['length_of_encounter_seconds'])}")
		if "recent_reports" not in st.session_state:
			st.session_state["recent_reports"] = []
		st.session_state["recent_reports"] = [selected_id] + [item for item in st.session_state["recent_reports"] if item != selected_id]
		st.session_state["recent_reports"] = st.session_state["recent_reports"][:5]
		favorite_ids = load_ids(FAVORITES_FILE)
		action_cols = st.columns(3)
		with action_cols[0]:
			if selected_id in favorite_ids:
				if st.button("Remove bookmark", key="remove_bookmark", icon=":material/bookmark_remove:"):
					if remove_id(FAVORITES_FILE, selected_id):
						st.rerun()
					st.error("The bookmark could not be removed locally.")
			else:
				if st.button("Bookmark sighting", key="add_bookmark", icon=":material/bookmark:"):
					if save_row(FAVORITES_FILE, {"record_id": selected_id, "saved_at": datetime.now().isoformat(timespec="seconds")}):
						st.rerun()
					st.error("The bookmark could not be saved locally.")
		with action_cols[1]:
			st.markdown(f"[Share this sighting]({record['source_url']})")
		with action_cols[2]:
			st.caption(f"{len(favorite_ids)} bookmarked")
		left, right = st.columns([1.2, 1])
		with left:
			st.markdown(f"### {html.escape(str(record['city']).title())}, {record['country_label']}")
			st.write(record["description"] or "No narrative description was supplied.")
			st.info(f"Local summary: {summarize_description(record['description'])}")
		with right:
			st.markdown("**Record details**")
			st.write(f"Reported: {record['date_label']}")
			st.write(f"Shape: {record['shape'].title()}")
			st.write(f"Duration: {format_duration(record['length_of_encounter_seconds'])}")
			st.write(f"Documented: {record['date_documented'] if pd.notna(record['date_documented']) else 'Not supplied'}")
			st.write(f"Coordinates: {record['latitude']:.5f}, {record['longitude']:.5f}")
			st.write(f"Assessment: {record['status']}")
			st.write(f"Entity: {record['entity_type']}")
			st.write(f"Source confidence: {record['confidence_label']} ({record['completeness_score']}% fields present)")
			st.write(f"Possible duplicate: {'Yes, review nearby records' if record['possible_duplicate'] else 'No matching record detected'}")
			st.caption("Confidence is based on field completeness, not truth or authenticity. Status and entity are heuristic classifications.")
			for label, url in map_links(record).items():
				st.markdown(f"[{label}]({url})")
			st.download_button("Export selected JSON", json.dumps(record.to_dict(), default=str, indent=2), "selected_sighting.json", "application/json", icon=":material/data_object:")
			st.caption("Audio, sketches, clippings, and video links are not present in the uploaded spreadsheet for this record.")

		with st.expander("Recent reports", expanded=False):
			recent_rows = filtered_by_id.loc[[item for item in st.session_state["recent_reports"] if item in filtered_by_id.index], ["date_label", "city", "shape"]]
			st.dataframe(recent_rows, width="stretch", hide_index=True)

		st.subheader("Community notes")
		vote_cols = st.columns(2)
		with vote_cols[0]:
			if st.button("Credible", key="credible_vote", icon=":material/thumb_up:"):
				st.session_state[f"vote_{selected_id}"] = "Credible"
		with vote_cols[1]:
			if st.button("Needs review", key="review_vote", icon=":material/flag:"):
				st.session_state[f"vote_{selected_id}"] = "Needs review"
		if st.session_state.get(f"vote_{selected_id}"):
			st.caption(f"Your vote: {st.session_state[f'vote_{selected_id}']}")
		with st.form("sighting_comment", clear_on_submit=True):
			comment = st.text_area("Add an investigation note", placeholder="What should other researchers notice?", height=80)
			commenter = st.text_input("Name (optional)")
			if st.form_submit_button("Post note", icon=":material/chat:") and comment.strip():
				saved = save_row(COMMENTS_FILE, {"record_id": selected_id, "posted_at": datetime.now().isoformat(timespec="seconds"), "name": commenter or "Anonymous", "comment": comment.strip()})
				st.success("Note added locally.") if saved else st.error("The note could not be saved locally.")
		if COMMENTS_FILE.exists():
			try:
				comments = pd.read_csv(COMMENTS_FILE)
				if {"record_id", "name", "comment", "posted_at"}.issubset(comments.columns):
					st.dataframe(comments[comments["record_id"].astype(str) == str(selected_id)][["name", "comment", "posted_at"]], width="stretch", hide_index=True)
			except (OSError, pd.errors.ParserError):
				st.warning("Saved community notes could not be read.")

		with st.expander("Similar reports", expanded=False):
			similar = data[(data["record_id"] != selected_id) & (data["shape"] == record["shape"])].copy()
			similar["distance"] = ((similar["latitude"] - record["latitude"]) ** 2 + ((similar["longitude"] - record["longitude"]) * 0.72) ** 2) ** 0.5
			st.dataframe(similar.sort_values(["year", "distance"], ascending=[False, True]).head(6)[["date_label", "city", "country_label", "shape", "description"]], width="stretch", hide_index=True)

		st.subheader("Nearby sightings from the same year")
		nearby = data[data["year"].eq(record["year"])].copy()
		radius_km = st.slider("Nearby search radius (km)", 10, 1000, 250)
		lat_delta = nearby["latitude"] - record["latitude"]
		lon_delta = (nearby["longitude"] - record["longitude"]) * 0.72
		nearby["distance"] = ((lat_delta ** 2 + lon_delta ** 2) ** 0.5) * 111
		nearby = nearby[nearby["distance"] <= radius_km]
		nearby_rows = []
		for _, nearby_record in nearby.sort_values("distance").head(8).iterrows():
			description = html.escape(str(nearby_record["description"] or "No description supplied."))
			if len(description) > 155:
				description = f"{description[:155]}..."
			nearby_rows.append(
				f"<tr><td>{html.escape(str(nearby_record['date_label']))}</td>"
				f"<td>{html.escape(str(nearby_record['city']).title())}</td>"
				f"<td>{html.escape(str(nearby_record['country_label']))}</td>"
				f"<td><span class='shape-badge'>{html.escape(str(nearby_record['shape']).title())}</span></td>"
				f"<td>{description}</td></tr>"
			)
		st.markdown(
			"<div class='nearby-table'><table><thead><tr><th>Date</th><th>Location</th><th>Country</th><th>Shape</th><th>Signal notes</th></tr></thead>"
			f"<tbody>{''.join(nearby_rows)}</tbody></table></div>",
			unsafe_allow_html=True,
		)


if __name__ == "__main__":
	main()
