import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import MarkerCluster, FeatureGroupSubGroup

# Загрузка данных
issues_df = pd.read_csv('sources/complete_issues_data.csv')

# Загрузка границ земель и преобразование в WGS84
states = gpd.read_file("vg5000_12-31.gk3.shape.ebenen/vg5000_ebenen_1231/VG5000_LAN.shp")
states_wgs84 = states.to_crs("EPSG:4326")

# Подсчёт проблем по землям
issues_per_state = issues_df.groupby('state').size().reset_index(name='issue_count')
states_with_data = states_wgs84.merge(issues_per_state, left_on='GEN', right_on='state', how='left')

# Преобразуем datetime-колонки в строки
for col in states_with_data.columns:
    if pd.api.types.is_datetime64_any_dtype(states_with_data[col]):
        states_with_data[col] = states_with_data[col].astype(str)

# Создание карты
m = folium.Map(location=[51.0, 10.0], zoom_start=6)

# Хлороплет
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

# Подсказки по регионам
folium.GeoJson(
    states_with_data,
    name='State Info',
    tooltip=folium.features.GeoJsonTooltip(
        fields=['GEN', 'issue_count'],
        aliases=['State:', 'Issues:'],
        localize=True
    )
).add_to(m)

# === ГРУППА: Все точки ===
all_points_group = folium.FeatureGroup(name="(A) Show category-unfiltered issues", show=True)
all_cluster = MarkerCluster().add_to(all_points_group)

for _, row in issues_df.iterrows():
    lat, lon = row.get('latitude'), row.get('longitude')
    if pd.notna(lat) and pd.notna(lon):
        folium.Marker(
            [lat, lon],
            popup=f"{row.get('category', 'No category')}: {str(row.get('description', ''))[:100]}..."
        ).add_to(all_cluster)

m.add_child(all_points_group)

# === ГРУППА: Категориальные точки ===
filtered_group = folium.FeatureGroup(name="(B) Show category-filtered issues", show=False)
filtered_cluster = MarkerCluster().add_to(filtered_group)
m.add_child(filtered_group)

# Создаем подгруппы по категориям
category_groups = {}
categories = sorted(issues_df['category'].dropna().unique())

for category in categories:
    subgroup = FeatureGroupSubGroup(filtered_cluster, category)
    m.add_child(subgroup)
    category_groups[category] = subgroup

# Добавим маркеры по категориям
for _, row in issues_df.iterrows():
    lat, lon = row.get('latitude'), row.get('longitude')
    category = row.get('category')
    if pd.notna(lat) and pd.notna(lon) and category in category_groups:
        folium.Marker(
            [lat, lon],
            popup=f"{category}: {str(row.get('description', ''))[:100]}..."
        ).add_to(category_groups[category])

# Панель управления
folium.LayerControl(collapsed=False).add_to(m)

# Сохраняем
m.save('germany_issues_working_toggle.html')
