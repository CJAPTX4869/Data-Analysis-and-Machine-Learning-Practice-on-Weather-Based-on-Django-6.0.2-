"""天气数据视图 - 首页、城市详情等"""
import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.db.models import Avg, Count
from django.utils import timezone
from .models import City, WeatherData
from .utils import (
    get_stat_overview, get_map_data, get_city_monthly_data,
    get_monthly_temp_stats
)


def index(request):
    """首页 - 统计卡片 + 全国城市地图 + 按省份城市列表"""
    stats = get_stat_overview()
    from django.utils import timezone
    today = timezone.now().date()

    # 地图数据：所有城市级，取最新的温度
    map_data = []
    for city in City.objects.filter(level='city'):
        w = WeatherData.objects.filter(city=city, date=today).first()
        if not w:
            w = WeatherData.objects.filter(city=city).order_by('-date').first()
        if w:
            map_data.append({
                'id': city.id, 'name': city.name, 'value': w.temperature_high,
                'lng': city.longitude, 'lat': city.latitude,
                'province': city.province, 'temp_low': w.temperature_low,
                'weather': w.weather_condition, 'aqi': w.aqi, 'aqi_level': w.aqi_level,
                'humidity': w.humidity, 'precipitation': w.precipitation,
            })

    # 按省份分组（用于右侧列表）
    from collections import OrderedDict
    provinces_dict = OrderedDict()
    for city in City.objects.filter(level='city').order_by('province', 'name'):
        p = city.province
        if p not in provinces_dict:
            provinces_dict[p] = []
        provinces_dict[p].append({'id': city.id, 'name': city.name, 'is_key': city.is_key})

    # 湖北重点：武汉黄石区+全部街镇
    wuhan = City.objects.filter(name='武汉', province='湖北', level='city').first()
    huangshi = City.objects.filter(name='黄石', province='湖北', level='city').first()
    wuhan_today = WeatherData.objects.filter(city=wuhan, date=today).first() if wuhan else None
    huangshi_today = WeatherData.objects.filter(city=huangshi, date=today).first() if huangshi else None

    # 武汉各区及其全部街镇
    wuhan_structure = []
    all_district_ids = []
    if wuhan:
        for dist in City.objects.filter(parent=wuhan, level='district').order_by('sort_order'):
            towns = list(City.objects.filter(parent=dist, level='town').order_by('sort_order').values('id', 'name'))
            wuhan_structure.append({'district': dist, 'towns': towns})
            all_district_ids.append(dist.id)
            all_district_ids.extend([t['id'] for t in towns])

    # 黄石各区县及其全部街镇
    huangshi_structure = []
    if huangshi:
        for dist in City.objects.filter(parent=huangshi, level='district').order_by('sort_order'):
            towns = list(City.objects.filter(parent=dist, level='town').order_by('sort_order').values('id', 'name'))
            huangshi_structure.append({'district': dist, 'towns': towns})
            all_district_ids.append(dist.id)
            all_district_ids.extend([t['id'] for t in towns])

    context = {
        'stats': stats,
        'map_data': json.dumps(map_data, ensure_ascii=False),
        'provinces_dict': provinces_dict,
        'wuhan': wuhan, 'wuhan_structure': wuhan_structure, 'wuhan_today': wuhan_today,
        'huangshi': huangshi, 'huangshi_structure': huangshi_structure, 'huangshi_today': huangshi_today,
        'all_district_ids': json.dumps(all_district_ids),
    }
    return render(request, 'index.html', context)


def city_detail(request, city_id):
    """城市天气详情页 - 支持日期范围查询"""
    city = get_object_or_404(City, pk=city_id)
    start_date = request.GET.get('start', '')
    end_date = request.GET.get('end', '')

    base_qs = WeatherData.objects.filter(city=city)
    if start_date:
        base_qs = base_qs.filter(date__gte=start_date)
    if end_date:
        base_qs = base_qs.filter(date__lte=end_date)

    weather_data = base_qs.order_by('-date')[:180]

    # 温度趋势数据
    temp_qs = base_qs.order_by('date')[:180]
    temp_data = list(temp_qs.values('date', 'temperature_high', 'temperature_low'))

    # 天气状况分布
    condition_dist = base_qs.values('weather_condition').annotate(
        count=Count('id')
    ).order_by('-count')[:8]

    # AQI趋势
    aqi_qs = base_qs.order_by('date')[:180]
    aqi_data = list(aqi_qs.values('date', 'aqi'))

    context = {
        'city': city,
        'weather_data': weather_data,
        'start_date': start_date,
        'end_date': end_date,
        'total_days': base_qs.count(),
        'temp_data': json.dumps([{
            'date': str(d['date']),
            'high': d['temperature_high'],
            'low': d['temperature_low']
        } for d in temp_data], ensure_ascii=False),
        'condition_dist': json.dumps([{
            'name': c['weather_condition'],
            'value': c['count']
        } for c in condition_dist], ensure_ascii=False),
        'aqi_data': json.dumps([{
            'date': str(d['date']),
            'aqi': d['aqi']
        } for d in aqi_data if d['aqi'] is not None], ensure_ascii=False),
        'precip_data': json.dumps([{
            'date': str(d['date']),
            'precipitation': d['precipitation']
        } for d in base_qs.order_by('date')[:180].values('date', 'precipitation')], ensure_ascii=False),
        'humidity_data': json.dumps([{
            'date': str(d['date']),
            'humidity': d['humidity']
        } for d in base_qs.order_by('date')[:180].values('date', 'humidity') if d['humidity'] is not None], ensure_ascii=False),
    }
    return render(request, 'city_analysis.html', context)


def api_city_data(request, city_id):
    """API: 获取城市天气数据 - 支持日期范围"""
    city = get_object_or_404(City, pk=city_id)
    qs = WeatherData.objects.filter(city=city)
    start = request.GET.get('start', '')
    end = request.GET.get('end', '')
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    data = qs.order_by('-date')[:180]
    result = [{
        'date': str(d.date),
        'temperature_high': d.temperature_high,
        'temperature_low': d.temperature_low,
        'weather_condition': d.weather_condition,
        'wind_direction': d.wind_direction,
        'wind_power': d.wind_power,
        'aqi': d.aqi,
        'aqi_level': d.aqi_level,
        'humidity': d.humidity,
        'precipitation': d.precipitation,
    } for d in data]
    return JsonResponse({'city': city.name, 'data': result})


def api_map_data(request):
    """API: 获取地图数据"""
    map_data = get_map_data()
    return JsonResponse({'data': map_data})


def api_yearly_daily(request):
    """API: 返回全年每日气温数据（支持城市筛选）"""
    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')
    province = request.GET.get('province', '')

    filters = {'date__year': year}
    if city_id:
        filters['city_id'] = int(city_id)
    elif province:
        filters['city__province'] = province
        filters['city__level'] = 'city'
    else:
        filters['city__level'] = 'city'

    qs = WeatherData.objects.filter(**filters).values('date').annotate(
        avg_high=Avg('temperature_high'),
        avg_low=Avg('temperature_low'),
    ).order_by('date')

    monthly = {}
    for item in qs:
        m = item['date'].month
        if m not in monthly:
            monthly[m] = {'dates': [], 'highs': [], 'lows': []}
        monthly[m]['dates'].append(str(item['date']))
        monthly[m]['highs'].append(round(item['avg_high'], 1))
        monthly[m]['lows'].append(round(item['avg_low'], 1))

    return JsonResponse({'year': year, 'province': province, 'monthly': monthly})


def api_batch_weather(request):
    """API: 批量获取多个城市的今日天气"""
    ids_str = request.GET.get('ids', '')
    if not ids_str:
        return JsonResponse({'data': []})
    ids = [int(i) for i in ids_str.split(',') if i.strip().isdigit()]
    today = timezone.now().date()
    result = {}
    for cid in ids:
        try:
            city = City.objects.get(pk=cid)
            w = WeatherData.objects.filter(city=city, date=today).first()
            if not w:
                w = WeatherData.objects.filter(city=city).order_by('-date').first()
            if w:
                result[str(cid)] = {
                    'name': city.name,
                    'temperature_high': w.temperature_high,
                    'temperature_low': w.temperature_low,
                    'weather_condition': w.weather_condition,
                    'aqi': w.aqi,
                    'aqi_level': w.aqi_level,
                    'humidity': w.humidity,
                    'precipitation': w.precipitation,
                }
        except City.DoesNotExist:
            pass
    return JsonResponse(result)
