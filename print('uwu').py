import geopandas as gpd
import pandas as pd
import folium

# Load issues data
issues_df = pd.read_csv('../data/challenge_2/complete_issues_data.csv')

# Load state boundaries and convert to web-friendly projection
states = gpd.read_file("../public_data/vg5000_12-31.gk3.shape.ebenen/vg5000_ebenen_1231/VG5000_LAN.shp")
states_wgs84 = states.to_crs("EPSG:4326")

# Count issues per state
issues_per_state = issues_df.groupby('state').size().reset_index(name='issue_count')

# Merge with geodata
states_with_data = states_wgs84.merge(issues_per_state, left_on='GEN', right_on='state', how='left')

# Create choropleth map
m = folium.Map(location=[51.0, 10.0], zoom_start=6)

folium.Choropleth(
    geo_data=states_with_data.to_json(),
    name='Issues by State',
    data=states_with_data,
    columns=['GEN', 'issue_count'],
    key_on='feature.properties.GEN',
    fill_color='YlOrRd',
    fill_opacity=0.7,
    line_opacity=0.2,
    legend_name='Number of Issues'
).add_to(m)

# Add tooltips
folium.features.GeoJson(
    states_with_data,
    name='State Info',
    tooltip=folium.features.GeoJsonTooltip(
        fields=['GEN', 'issue_count'],
        aliases=['State:', 'Issues:'],
        localize=True
    )
).add_to(m)

m.save('germany_issues_choropleth.html')


### Advanced: Combine Points with Boundaries

# Create base map with state boundaries
m = folium.Map(location=[51.0, 10.0], zoom_start=6)

# Add state boundaries as base layer
folium.GeoJson(
    states_wgs84.to_json(),
    style_function=lambda x: {
        'fillColor': 'lightblue',
        'color': 'black',
        'weight': 1,
        'fillOpacity': 0.1
    }
).add_to(m)

# Add individual issues as markers on top
marker_cluster = MarkerCluster().add_to(m)
for idx, row in issues_df.iterrows():
    folium.Marker(
        [row['latitude'], row['longitude']],
        popup=f"{row['category']}: {row['description'][:50]}..."
    ).add_to(marker_cluster)