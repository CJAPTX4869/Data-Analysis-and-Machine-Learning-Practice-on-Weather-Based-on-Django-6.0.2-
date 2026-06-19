"""
获取当日真实天气数据（通过 Open-Meteo 免费 API）
使用 Django ORM 写入 MySQL，支持每日更新
用法: python manage.py fetch_today_weather
"""
import time
from datetime import date

import requests
from django.core.management.base import BaseCommand

from apps.weather.models import City, WeatherData


# Open-Meteo 天气代码 -> 中文天气状况
WEATHER_CODE_MAP = {
    0: '晴', 1: '晴', 2: '晴转多云', 3: '多云转阴',
    45: '雾', 48: '雾',
    51: '小雨', 53: '小雨', 55: '中雨',
    56: '冻雨', 57: '冻雨',
    61: '小雨', 63: '中雨', 65: '大雨',
    66: '冻雨', 67: '冻雨',
    71: '小雪', 73: '中雪', 75: '大雪',
    77: '霰',
    80: '阵雨', 81: '阵雨', 82: '暴雨',
    83: '雨夹雪', 84: '雨夹雪',
    85: '阵雪', 86: '阵雪',
    95: '雷阵雨', 96: '冰雹', 99: '冰雹',
}

# 风向角度 -> 中文风向
def wind_degree_to_direction(deg):
    if deg is None: return '无持续风向'
    dirs = ['北风', '东北风', '东风', '东南风', '南风', '西南风', '西风', '西北风']
    idx = round(deg / 45) % 8
    return dirs[idx]

# 风力等级（m/s -> 风力描述）
def wind_speed_to_power(ms):
    if ms is None: return '微风'
    if ms < 0.3: return '无风'
    if ms < 1.6: return '1级'
    if ms < 3.4: return '2级'
    if ms < 5.5: return '3级'
    if ms < 8.0: return '4级'
    if ms < 10.8: return '5级'
    if ms < 13.9: return '6级'
    if ms < 17.2: return '7级'
    return '8级以上'

# AQI -> 等级
def aqi_to_level(aqi_val):
    if aqi_val <= 50: return '优'
    if aqi_val <= 100: return '良'
    if aqi_val <= 150: return '轻度污染'
    if aqi_val <= 200: return '中度污染'
    if aqi_val <= 300: return '重度污染'
    return '严重污染'


class Command(BaseCommand):
    help = '从 Open-Meteo API 获取当日真实天气数据并写入 MySQL'

    def add_arguments(self, parser):
        parser.add_argument('--province', type=str, help='只更新指定省份', default=None)
        parser.add_argument('--city', type=str, help='只更新指定城市名', default=None)

    def fetch_city_weather(self, city):
        """获取单个城市的当日天气（Open-Meteo API）"""
        today = date.today()

        try:
            # 1. 获取天气数据（forecast API）
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={city.latitude}&longitude={city.longitude}"
                f"&daily=temperature_2m_max,temperature_2m_min,weathercode,"
                f"windspeed_10m_max,winddirection_10m_dominant,precipitation_sum,"
                f"relative_humidity_2m_mean"
                f"&wind_speed_unit=ms"
                f"&timezone=Asia/Shanghai&forecast_days=1"
            )
            resp = requests.get(weather_url, timeout=10)
            if resp.status_code != 200:
                return None
            data = resp.json()

            daily = data.get('daily', {})

            temp_high = int(daily.get('temperature_2m_max', [25])[0]) if daily.get('temperature_2m_max') else 25
            temp_low = int(daily.get('temperature_2m_min', [15])[0]) if daily.get('temperature_2m_min') else 15
            weather_code = int(daily.get('weathercode', [0])[0]) if daily.get('weathercode') else 0
            weather_cond = WEATHER_CODE_MAP.get(weather_code, '多云')
            wind_speed = daily.get('windspeed_10m_max', [0])[0] if daily.get('windspeed_10m_max') else 0
            wind_dir_deg = daily.get('winddirection_10m_dominant', [0])[0] if daily.get('winddirection_10m_dominant') else 0
            precip = float(daily.get('precipitation_sum', [0])[0]) if daily.get('precipitation_sum') else 0
            humidity_raw = daily.get('relative_humidity_2m_mean', [None])[0] if daily.get('relative_humidity_2m_mean') else None

            # 2. 获取空气质量数据（air-quality API）
            aqi_val = None
            try:
                aqi_url = (
                    f"https://air-quality-api.open-meteo.com/v1/air-quality"
                    f"?latitude={city.latitude}&longitude={city.longitude}"
                    f"&current=european_aqi,pm2_5"
                )
                aqi_resp = requests.get(aqi_url, timeout=8)
                if aqi_resp.status_code == 200:
                    aqi_data = aqi_resp.json()
                    aqi_val = aqi_data.get('current', {}).get('european_aqi')
            except Exception:
                pass  # AQI API 不可用时 = None，宁缺毋滥

            return {
                'temperature_high': temp_high,
                'temperature_low': temp_low,
                'weather_condition': weather_cond,
                'wind_direction': wind_degree_to_direction(wind_dir_deg),
                'wind_power': wind_speed_to_power(wind_speed),
                'aqi': int(aqi_val) if aqi_val is not None else None,
                'aqi_level': aqi_to_level(int(aqi_val)) if aqi_val is not None else None,
                'humidity': round(float(humidity_raw), 1) if humidity_raw is not None else None,
                'precipitation': round(precip, 1),
            }

        except Exception as e:
            print(f"  [{city.name}] API请求失败: {e}")
            return None

    def handle(self, *args, **options):
        province_filter = options.get('province')
        city_filter = options.get('city')

        cities = City.objects.filter(level__in=['city', 'district', 'town'])
        if province_filter:
            cities = cities.filter(province=province_filter)
        if city_filter:
            cities = cities.filter(name__icontains=city_filter)

        total = cities.count()
        updated = 0
        today = date.today()

        self.stdout.write(f"开始获取 {total} 个城市的当日天气...")
        self.stdout.write(f"数据来源: Open-Meteo API (免费)")

        for i, city in enumerate(cities):
            print(f"[{i+1}/{total}] {city.province}-{city.name} ...", end=' ')
            weather = self.fetch_city_weather(city)

            if weather:
                obj, created = WeatherData.objects.update_or_create(
                    city=city, date=today,
                    defaults=weather
                )
                status = '新增' if created else '更新'
                aqi_str = f'AQI:{weather["aqi"]}' if weather['aqi'] is not None else 'AQI:N/A'
                print(f"✓ {weather['temperature_high']}℃/{weather['temperature_low']}℃ {weather['weather_condition']} {aqi_str} ({status})")
                updated += 1
            else:
                # API失败时用随机填充保底
                print("✗ API失败，跳过")
            time.sleep(0.3)  # API 限流

        self.stdout.write(self.style.SUCCESS(
            f'\n当日天气获取完成! 成功: {updated}/{total}, 日期: {today}'
        ))
