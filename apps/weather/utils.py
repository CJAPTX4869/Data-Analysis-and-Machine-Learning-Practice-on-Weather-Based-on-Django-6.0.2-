"""天气数据处理工具函数"""
from datetime import datetime, timedelta
from django.db.models import Avg, Max, Min, Count, Sum, Q
from django.utils import timezone
from .models import City, WeatherData


def get_stat_overview():
    """获取首页统计概览"""
    total_cities = City.objects.filter(level='city').count()
    total_records = WeatherData.objects.count()
    today = timezone.now().date()

    # 今日数据
    today_data = WeatherData.objects.filter(date=today)
    if today_data.exists():
        avg_high = today_data.aggregate(Avg('temperature_high'))['temperature_high__avg'] or 0
        avg_low = today_data.aggregate(Avg('temperature_low'))['temperature_low__avg'] or 0
        avg_aqi = today_data.aggregate(Avg('aqi'))['aqi__avg'] or 0
    else:
        recent = WeatherData.objects.order_by('-date')[:50]
        avg_high = recent.aggregate(Avg('temperature_high'))['temperature_high__avg'] or 0
        avg_low = recent.aggregate(Avg('temperature_low'))['temperature_low__avg'] or 0
        avg_aqi = recent.aggregate(Avg('aqi'))['aqi__avg'] or 0

    # 湖北省统计数据
    hubei_cities = City.objects.filter(province='湖北', level='city')
    hubei_ids = list(hubei_cities.values_list('id', flat=True))
    hubei_weather = WeatherData.objects.filter(city_id__in=hubei_ids, date=today)
    hubei_count = hubei_weather.count()

    # 武汉+黄石重点区域
    key_cities = City.objects.filter(province='湖北', is_key=True)

    return {
        'total_cities': total_cities,
        'total_records': total_records,
        'avg_high': round(avg_high, 1),
        'avg_low': round(avg_low, 1),
        'avg_aqi': round(avg_aqi, 1),
        'hubei_city_count': hubei_cities.count(),
        'hubei_weather_count': hubei_count,
        'key_cities': key_cities,
    }


def get_map_data():
    """获取中国地图热力图数据"""
    cities = City.objects.all()
    today = timezone.now().date()

    map_data = []
    for city in cities:
        data = WeatherData.objects.filter(city=city, date=today).first()
        if not data:
            data = WeatherData.objects.filter(city=city).order_by('-date').first()
        if data:
            map_data.append({
                'name': city.name,
                'value': data.temperature_high,
                'lng': city.longitude,
                'lat': city.latitude,
                'province': city.province,
                'temp_low': data.temperature_low,
                'weather': data.weather_condition,
                'aqi': data.aqi,
                'aqi_level': data.aqi_level,
                'humidity': data.humidity,
                'precipitation': data.precipitation,
            })

    return map_data


def get_city_monthly_data(city_id: int = None, year: int = None, month: int = None):
    """获取城市月度天气数据"""
    if not year:
        year = timezone.now().year
    if not month:
        month = timezone.now().month

    queryset = WeatherData.objects.filter(date__year=year)
    if city_id:
        queryset = queryset.filter(city_id=city_id)

    if month:
        queryset = queryset.filter(date__month=month)

    return queryset.select_related('city').order_by('date')


def get_monthly_temp_stats(year: int = None):
    """获取月度气温统计数据"""
    if not year:
        year = timezone.now().year

    monthly_stats = []
    for month in range(1, 13):
        data = WeatherData.objects.filter(date__year=year, date__month=month)
        if data.exists():
            monthly_stats.append({
                'month': f'{month}月',
                'avg_high': round(data.aggregate(Avg('temperature_high'))['temperature_high__avg'] or 0, 1),
                'avg_low': round(data.aggregate(Avg('temperature_low'))['temperature_low__avg'] or 0, 1),
                'max_temp': data.aggregate(Max('temperature_high'))['temperature_high__max'] or 0,
                'min_temp': data.aggregate(Min('temperature_low'))['temperature_low__min'] or 0,
            })

    return monthly_stats


def get_aqi_monthly_stats(year: int = None):
    """获取月度空气质量统计数据"""
    if not year:
        year = timezone.now().year

    aqi_stats = []
    for month in range(1, 13):
        data = WeatherData.objects.filter(date__year=year, date__month=month)
        if data.exists():
            avg_aqi = data.aggregate(Avg('aqi'))['aqi__avg'] or 0
            good_days = data.filter(aqi__lte=50).count()
            moderate_days = data.filter(aqi__gt=50, aqi__lte=100).count()
            polluted_days = data.filter(aqi__gt=100).count()
            aqi_stats.append({
                'month': f'{month}月',
                'avg_aqi': round(avg_aqi, 1),
                'good_days': good_days,
                'moderate_days': moderate_days,
                'polluted_days': polluted_days,
            })

    return aqi_stats


def get_wind_data(city_id: int = None):
    """获取风力统计数据"""
    queryset = WeatherData.objects.all()
    if city_id:
        queryset = queryset.filter(city_id=city_id)

    wind_directions = queryset.values('wind_direction').annotate(
        count=Count('id')
    ).order_by('-count')

    return list(wind_directions)


def get_weather_text_for_wordcloud():
    """获取天气状况文本用于生成词云"""
    conditions = WeatherData.objects.values('weather_condition').annotate(
        count=Count('id')
    ).order_by('-count')

    text_parts = []
    for item in conditions:
        condition = item['weather_condition']
        count = item['count']
        text_parts.extend([condition] * min(count, 100))

    return ' '.join(text_parts)
