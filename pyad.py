import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import MarkerCluster, FeatureGroupSubGroup
from folium import IFrame
import panel as pn
import pathlib
import uuid

pn.extension(sizing_mode="stretch_both")

# === Load data ===
issues_df = pd.read_csv("sources/complete_issues_data.csv").dropna(subset=["latitude", "longitude"])

def clean_category(cat):
    if isinstance(cat, str):
        return cat.replace("Category: ", "").strip()
    return cat

issues_df["category"] = issues_df["category"].apply(clean_category)

# Load shapefile
states = gpd.read_file("vg5000_12-31.gk3.shape.ebenen/vg5000_ebenen_1231/VG5000_LAN.shp").to_crs("EPSG:4326")
issues_per_state = issues_df.groupby("state").size().reset_index(name="issue_count")
states_with_data = states.merge(issues_per_state, left_on="GEN", right_on="state", how="left")

# Convert datetime columns to string
for df in [states_with_data, issues_df]:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)

# === Widgets ===
popup_fields = []
field_selector = pn.widgets.CheckBoxGroup(name="Popup fields", value=[], options=popup_fields)

gender_selector = pn.widgets.Select(
    name="Gender",
    options=[""] + sorted(issues_df["gender"].dropna().unique().tolist())
)
age_selector = pn.widgets.Select(
    name="Age Group",
    options=[""] + sorted(issues_df["age_group"].dropna().unique().tolist())
)
origin_selector = pn.widgets.Select(
    name="Origin",
    options=[""] + sorted(issues_df["origin"].dropna().unique().tolist())
)

lat_slider = pn.widgets.RangeSlider(
    name="Latitude Range",
    start=issues_df["latitude"].min(),
    end=issues_df["latitude"].max(),
    step=0.1,
    value=(issues_df["latitude"].min(), issues_df["latitude"].max())
)
lon_slider = pn.widgets.RangeSlider(
    name="Longitude Range",
    start=issues_df["longitude"].min(),
    end=issues_df["longitude"].max(),
    step=0.1,
    value=(issues_df["longitude"].min(), issues_df["longitude"].max())
)

state_selector = pn.widgets.Select(
    name="State", options=[""] + sorted(issues_df["state"].dropna().unique())
)
district_selector = pn.widgets.Select(name="District", options=[""])
municipality_selector = pn.widgets.Select(name="Municipality", options=[""])

category_mode = pn.widgets.RadioButtonGroup(
    name="Mode", options=["(A) Show All Issues", "(B) Filter by Category"], button_type="primary", value="(A) Show All Issues"
)
all_categories = sorted(issues_df["category"].dropna().unique())
category_selector = pn.widgets.CheckBoxGroup(name="Select categories", options=all_categories, value=[])

# === Dynamic update of district/municipality options ===
@pn.depends(state_selector.param.value, watch=True)
def update_districts_and_municipalities(state):
    if state:
        filtered_df = issues_df[issues_df["state"] == state]
        district_selector.options = [""] + sorted(filtered_df["district"].dropna().unique())
        municipality_selector.options = [""] + sorted(filtered_df["municipality"].dropna().unique())
    else:
        district_selector.options = [""] + sorted(issues_df["district"].dropna().unique())
        municipality_selector.options = [""] + sorted(issues_df["municipality"].dropna().unique())

# === Map generation ===
def update_map(selected_fields, lat_range, lon_range, district, municipality, state, mode, selected_categories, gender, age_group, origin):
    lat_min, lat_max = lat_range
    lon_min, lon_max = lon_range

    # Smart zoom
    center_lat, center_lon = 51.0, 10.0
    zoom = 6
    if municipality:
        muni_df = issues_df[issues_df["municipality"] == municipality]
        if not muni_df.empty:
            center_lat = muni_df["latitude"].mean()
            center_lon = muni_df["longitude"].mean()
            zoom = 12
    elif state:
        state_df = issues_df[issues_df["state"] == state]
        if not state_df.empty:
            center_lat = state_df["latitude"].mean()
            center_lon = state_df["longitude"].mean()
            zoom = 7

    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom)

    # Choropleth
    folium.Choropleth(
        geo_data=states_with_data.to_json(),
        name="Issues by State",
        data=states_with_data,
        columns=["GEN", "issue_count"],
        key_on="feature.properties.GEN",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Number of Issues"
    ).add_to(m)

    folium.GeoJson(
        states_with_data,
        name="State Info",
        tooltip=folium.features.GeoJsonTooltip(fields=["GEN", "issue_count"], aliases=["State:", "Issues:"], localize=True)
    ).add_to(m)

    # Filter data
    df = issues_df[
        (issues_df["latitude"] >= lat_min) & (issues_df["latitude"] <= lat_max) &
        (issues_df["longitude"] >= lon_min) & (issues_df["longitude"] <= lon_max)
    ]
    if state:
        df = df[df["state"] == state]
    if district:
        df = df[df["district"] == district]
    if municipality:
        df = df[df["municipality"] == municipality]

    # Add markers
    if mode.startswith("(A)"):
        cluster = MarkerCluster().add_to(m)
        for _, row in df.iterrows():
            html = f"""
                <div style="font-family:Arial, sans-serif; width:400px;">
                    <div style="font-weight:bold; font-size:14px; margin-bottom:10px;">
                        {row.get('category', 'No category')}
                    </div>
                    <div style="font-size:13px; line-height:1.4;">
                        {str(row.get('description', ''))}
                    </div>
                </div>
            """
            iframe = IFrame(html, width=444, height=111)
            popup = folium.Popup(iframe, max_width=500)
            folium.Marker([row["latitude"], row["longitude"]], popup=popup).add_to(cluster)

    elif mode.startswith("(B)"):
        cluster = MarkerCluster().add_to(m)
        if gender:
            df = df[df["gender"] == gender]
        if age_group:
            df = df[df["age_group"] == age_group]
        if origin:
            df = df[df["origin"] == origin]
        subgroups = {}
        for cat in selected_categories:
            sub = FeatureGroupSubGroup(cluster, cat)
            m.add_child(sub)
            subgroups[cat] = sub

        df_filtered = df[df["category"].isin(selected_categories)]
        for _, row in df_filtered.iterrows():
            html = f"""
                <div style="font-family:Arial, sans-serif; width:400px;">
                    <div style="font-weight:bold; font-size:14px; margin-bottom:5px;">
                        {row.get('category', 'No category')}
                    </div>
                    <div style="font-size:13px; line-height:1.4;">
                        {str(row.get('description', ''))}
                    </div>
                </div>
            """
            iframe = IFrame(html, width=444, height=111)
            popup = folium.Popup(iframe, max_width=500)
            cat = row["category"]
            if cat in subgroups:
                folium.Marker([row["latitude"], row["longitude"]], popup=popup).add_to(subgroups[cat])

    folium.LayerControl(collapsed=False).add_to(m)

    # Save map
    static_path = pathlib.Path(__file__).parent / "static"
    static_path.mkdir(exist_ok=True)
    map_path = static_path / "live_map_embedded.html"
    m.save(map_path)

    return pn.pane.HTML(
        f"<iframe src='/assets/live_map_embedded.html?v={uuid.uuid4()}' width='100%' height='1000' style='border:none;'></iframe>",
        sizing_mode="stretch_both"
    )

# === Reactive Map ===
map_view = pn.bind(
    update_map,
    selected_fields=field_selector,
    lat_range=lat_slider,
    lon_range=lon_slider,
    district=district_selector,
    municipality=municipality_selector,
    state=state_selector,
    mode=category_mode,
    gender=gender_selector,
    age_group=age_selector,
    origin=origin_selector,
    selected_categories=category_selector
)

# === Layout ===
sidebar = pn.Column(
    "# 🗺 Map Filters",
    category_mode,
    pn.Spacer(height=10),
    "## (A) Coordinate / Region Filters",
    lat_slider,
    lon_slider,
    state_selector,
    district_selector,
    municipality_selector,
    pn.Spacer(height=10),
    "## (B) Category Filters",
    pn.WidgetBox(category_selector, min_height = 600, max_height=600, scroll=True),  # Добавляем скролл
    pn.Spacer(height=10 ),
    gender_selector,
    age_selector,
    origin_selector,
    width=350,
    sizing_mode="stretch_height"
)


layout = pn.Row(
    sidebar,
    pn.Column(
        map_view,
        sizing_mode="stretch_both",
        min_width=700  # Можно увеличить при необходимости
    ),
    sizing_mode="stretch_both"
)
layout.servable()
