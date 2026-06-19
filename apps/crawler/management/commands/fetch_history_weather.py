"""
获取历史真实天气数据（Open-Meteo 历史归档 API）
用法: python manage.py fetch_history_weather --start 2025-06-01 --end 2026-06-05
"""
import time
from datetime import date, timedelta

import requests
from django.core.management.base import BaseCommand
from apps.weather.models import City, WeatherData

# 天气代码映射（与 fetch_today_weather 保持一致）
WEATHER_CODE_MAP = {
    0: '晴', 1: '晴', 2: '晴转多云', 3: '多云转阴',
    45: '雾', 48: '雾', 51: '小雨', 53: '小雨', 55: '中雨',
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

def wind_degree_to_direction(deg):
    if deg is None: return '无持续风向'
    dirs = ['北风', '东北风', '东风', '东南风', '南风', '西南风', '西风', '西北风']
    return dirs[round(deg / 45) % 8]

def wind_speed_to_power(ms):
    if ms is None: return '微风'
    if ms < 0.3: return '无风'
    if ms < 1.6: return '1级';
    if ms < 3.4: return '2级';
    if ms < 5.5: return '3级'
    if ms < 8.0: return '4级';
    if ms < 10.8: return '5级'
    if ms < 13.9: return '6级';
    if ms < 17.2: return '7级'
    return '8级以上'


class Command(BaseCommand):
    help = '从 Open-Meteo 历史API获取历史天气数据'

    def add_arguments(self, parser):
        parser.add_argument('--start', type=str, default='2025-06-01', help='开始日期')
        parser.add_argument('--end', type=str, default='2026-06-05', help='结束日期')
        parser.add_argument('--province', type=str, default='湖北', help='省份')
        parser.add_argument('--batch', type=int, default=30, help='每批城市数')

    def handle(self, *args, **options):
        start_date = options['start']
        end_date = options['end']
        province = options['province']
        batch_size = options['batch']

        cities = list(City.objects.filter(province=province, level__in=['city', 'district', 'town']))
        self.stdout.write(f'获取 {province} 省 {len(cities)} 个区域 {start_date}~{end_date} 历史天气...')

        total_created = 0
        total_updated = 0
        for i, city in enumerate(cities):
            self.stdout.write(f'[{i+1}/{len(cities)}] {city.name} ...', ending='')
            city_created = 0
            city_updated = 0
            try:
                url = (
                    f'https://archive-api.open-meteo.com/v1/archive'
                    f'?latitude={city.latitude}&longitude={city.longitude}'
                    f'&start_date={start_date}&end_date={end_date}'
                    f'&daily=temperature_2m_max,temperature_2m_min,weathercode,'
                    f'windspeed_10m_max,winddirection_10m_dominant,precipitation_sum,'
                    f'relative_humidity_2m_mean'
                    f'&wind_speed_unit=ms'
                    f'&timezone=Asia/Shanghai'
                )
                resp = requests.get(url, timeout=30)
                if resp.status_code != 200:
                    self.stdout.write(f' ✗ HTTP {resp.status_code}')
                    time.sleep(0.5)
                    continue

                data = resp.json()
                daily = data.get('daily', {})
                dates = daily.get('time', [])
                if not dates:
                    self.stdout.write(' ✗ 无数据')
                    time.sleep(0.5)
                    continue

                highs = daily.get('temperature_2m_max', [])
                lows = daily.get('temperature_2m_min', [])
                codes = daily.get('weathercode', [])
                winds = daily.get('windspeed_10m_max', [])
                winddirs = daily.get('winddirection_10m_dominant', [])
                precips = daily.get('precipitation_sum', [])
                humidities = daily.get('relative_humidity_2m_mean', [])

                # 获取历史 AQI（空气品质API支持历史回查）
                aqi_daily = {}
                try:
                    aqi_url = (
                        f'https://air-quality-api.open-meteo.com/v1/air-quality'
                        f'?latitude={city.latitude}&longitude={city.longitude}'
                        f'&start_date={start_date}&end_date={end_date}'
                        f'&hourly=european_aqi&timezone=Asia/Shanghai'
                    )
                    aqi_resp = requests.get(aqi_url, timeout=20)
                    if aqi_resp.status_code == 200:
                        aqi_data = aqi_resp.json()
                        aqi_hourly = aqi_data.get('hourly', {})
                        aqi_times = aqi_hourly.get('time', [])
                        aqi_vals = aqi_hourly.get('european_aqi', [])
                        # 按日聚合小时数据取日均
                        from collections import defaultdict
                        day_sums = defaultdict(list)
                        for t, v in zip(aqi_times, aqi_vals):
                            if v is not None:
                                day_sums[t[:10]].append(float(v))
                        for day_str, vals in day_sums.items():
                            if vals:
                                aqi_daily[day_str] = round(sum(vals) / len(vals))
                except Exception:
                    pass  # AQI API 不可用 → 保持 None

                for j, d in enumerate(dates):
                    wc = int(codes[j]) if j < len(codes) else 0
                    wd = int(winddirs[j]) if j < len(winddirs) else 0
                    ws = float(winds[j]) if j < len(winds) else 0
                    pr = float(precips[j]) if j < len(precips) else 0
                    hum = float(humidities[j]) if j < len(humidities) and humidities[j] is not None else None

                    # AQI 等级
                    aqi_val = aqi_daily.get(d)
                    aqi_lvl = None
                    if aqi_val is not None:
                        if aqi_val <= 50: aqi_lvl = '优'
                        elif aqi_val <= 100: aqi_lvl = '良'
                        elif aqi_val <= 150: aqi_lvl = '轻度污染'
                        elif aqi_val <= 200: aqi_lvl = '中度污染'
                        elif aqi_val <= 300: aqi_lvl = '重度污染'
                        else: aqi_lvl = '严重污染'

                    defaults = {
                        'temperature_high': int(highs[j]) if j < len(highs) else 25,
                        'temperature_low': int(lows[j]) if j < len(lows) else 15,
                        'weather_condition': WEATHER_CODE_MAP.get(wc, '多云'),
                        'wind_direction': wind_degree_to_direction(wd),
                        'wind_power': wind_speed_to_power(ws),
                        'precipitation': round(pr, 1),
                        'humidity': round(hum, 1) if hum is not None else None,
                        'aqi': aqi_val,
                        'aqi_level': aqi_lvl,
                    }
                    _, created = WeatherData.objects.update_or_create(
                        city=city, date=d,
                        defaults=defaults,
                    )
                    if created:
                        city_created += 1
                    else:
                        city_updated += 1

                self.stdout.write(f' ✓ {city_created}条新增 {city_updated}条更新')

            except Exception as e:
                self.stdout.write(f' ✗ {e}')

            total_created += city_created
            total_updated += city_updated
            time.sleep(0.3)

        self.stdout.write(self.style.SUCCESS(
            f'\n历史天气获取完成! 新增 {total_created} 条, 更新 {total_updated} 条'
        ))
