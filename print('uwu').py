import geopandas as gpd
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from folium import IFrame

# Загрузка данных о проблемах
issues_df = pd.read_csv('sources/complete_issues_data.csv')

# Загрузка границ земель и преобразование в WGS84
states = gpd.read_file("vg5000_12-31.gk3.shape.ebenen/vg5000_ebenen_1231/VG5000_LAN.shp")
states_wgs84 = states.to_crs("EPSG:4326")

# Подсчёт проблем по землям
issues_per_state = issues_df.groupby('state').size().reset_index(name='issue_count')

# Объединение геоданных с данными о проблемах
states_with_data = states_wgs84.merge(issues_per_state, left_on='GEN', right_on='state', how='left')

# Преобразуем datetime-колонки в строки (если есть)
states_with_data = states_with_data.copy()
for col in states_with_data.columns:
    if pd.api.types.is_datetime64_any_dtype(states_with_data[col]):
        states_with_data[col] = states_with_data[col].astype(str)

# Создание карты с хлороплетом
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

# Добавление маркеров проблем с кастомными popup
marker_cluster = MarkerCluster().add_to(m)

for idx, row in issues_df.iterrows():
    if pd.notna(row.get('latitude')) and pd.notna(row.get('longitude')):
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
        iframe = IFrame(html, width=500, height=111)
        popup = folium.Popup(iframe, max_width=500)



        folium.Marker(
            [row['latitude'], row['longitude']],
            popup=popup
        ).add_to(marker_cluster)
m.save('germany_issues_choropleth.html')
