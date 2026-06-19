"""数据分析视图 - 月度统计、AQI、风力、词云、预测、降水"""
import json
from io import BytesIO
import base64
from collections import OrderedDict
from datetime import date, timedelta

from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from apps.weather.models import City, WeatherData, PredictionResult
from apps.weather.utils import (
    get_monthly_temp_stats, get_aqi_monthly_stats,
    get_wind_data, get_weather_text_for_wordcloud,
)
from . import ml_model
from .ml_model import get_predictor


def _get_city_options(province_filter=None):
    """
    省→市→区→镇 层级下拉选项（1次查询+内存分组，避免N+1）
    格式: OrderedDict {省: [(id_str, label, level), ...]}
    """
    qs = City.objects.filter(level__in=['city', 'district', 'town']).select_related('parent')
    if province_filter:
        qs = qs.filter(province=province_filter)

    # 1次查询全部，按层级排序
    all_cities = list(qs.order_by('province', 'sort_order', 'name'))

    # 按 parent_id 建立索引（区→市，镇→区）
    children_by_parent = {}
    for c in all_cities:
        pid = c.parent_id
        if pid:
            children_by_parent.setdefault(pid, []).append(c)

    # 构建层级树
    result = OrderedDict()
    for c in all_cities:
        if c.level != 'city':
            continue
        prov = c.province
        if prov not in result:
            result[prov] = []
        result[prov].append((str(c.id), '　' + c.name, 'city'))

        # 区
        for dist in children_by_parent.get(c.id, []):
            result[prov].append((str(dist.id), '　　' + dist.name, 'district'))

            # 镇
            for town in children_by_parent.get(dist.id, []):
                result[prov].append((str(town.id), '　　　' + town.name, 'town'))

    return result


def monthly_stats(request):
    """月度气温统计页面 - 支持省份/城市筛选"""
    from django.utils import timezone
    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')
    prov = request.GET.get('prov', '')

    context = {
        'year': year,
        'city_tree': _get_city_options(prov if prov else None),
        'sel_city': city_id,
        'sel_prov': prov,
    }
    return render(request, 'monthly_stats.html', context)


def aqi_stats(request):
    """空气质量统计页面"""
    from django.utils import timezone
    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')

    context = {
        'year': year,
        'city_tree': _get_city_options(),
        'sel_city': city_id,
    }
    return render(request, 'aqi_stats.html', context)


def wind_analysis(request):
    """风力分析页面 - 支持年/月/城市筛选"""
    from django.utils import timezone
    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')

    context = {
        'year': year,
        'city_tree': _get_city_options(),
        'sel_city': city_id,
    }
    return render(request, 'wind_analysis.html', context)


def wordcloud_view(request):
    """词云图页面"""
    text_data = get_weather_text_for_wordcloud()

    # 生成词云图
    error_msg = None
    try:
        from wordcloud import WordCloud
        import jieba

        # 分词
        words = jieba.cut(text_data)
        word_text = ' '.join(words)

        wc = WordCloud(
            font_path='C:/Windows/Fonts/simhei.ttf',  # 黑体字体
            width=800,
            height=500,
            background_color='white',
            max_words=100,
            max_font_size=120,
            random_state=42,
        )

        # 如果没有足够文本数据，使用天气状况频率生成
        if len(word_text.strip()) < 50:
            # 从数据库获取天气状况词频
            from django.db.models import Count
            conditions = WeatherData.objects.values('weather_condition').annotate(
                count=Count('id')
            )
            freq_dict = {}
            for item in conditions:
                freq_dict[item['weather_condition']] = item['count']
            wc.generate_from_frequencies(freq_dict)
        else:
            wc.generate(word_text)

        # 转为 base64
        buffer = BytesIO()
        wc.to_image().save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        wordcloud_img = f'data:image/png;base64,{img_base64}'
    except Exception as e:
        wordcloud_img = None
        error_msg = str(e)
        print(f"词云生成失败: {e}")

    context = {
        'wordcloud_img': wordcloud_img,
        'error_msg': error_msg if 'error_msg' in locals() else None,
    }
    return render(request, 'wordcloud.html', context)


def _fetch_precip_forecast(city):
    """从 Open-Meteo 获取未来3天降水概率预报"""
    import requests
    try:
        url = (
            f'https://api.open-meteo.com/v1/forecast'
            f'?latitude={city.latitude}&longitude={city.longitude}'
            f'&daily=weathercode,precipitation_sum,precipitation_probability_mean'
            f'&forecast_days=3&timezone=Asia/Shanghai'
        )
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return None
        data = resp.json()
        daily = data.get('daily', {})
        dates = daily.get('time', [])
        codes = daily.get('weathercode', [])
        precip_amounts = daily.get('precipitation_sum', [])
        precip_probs = daily.get('precipitation_probability_mean', [])
        result = []
        for i in range(len(dates)):
            result.append({
                'date': dates[i],
                'weathercode': codes[i] if i < len(codes) else 0,
                'precip_mm': round(float(precip_amounts[i]), 1) if i < len(precip_amounts) and precip_amounts[i] is not None else 0,
                'precip_prob': int(precip_probs[i]) if i < len(precip_probs) and precip_probs[i] is not None else None,
            })
        return result
    except Exception:
        return None


def prediction(request):
    """天气预测页面 - 多模型对比"""
    prov = request.GET.get('prov', '')
    city_tree = _get_city_options(prov if prov else None)
    city_id = request.GET.get('city_id')
    selected_city = None
    all_predictions = {}
    accuracies = []
    best_model_name = ''
    recent_data = []
    precip_forecast = None

    stored_predictions = None
    stored_accuracy = None
    stored_model = None
    if city_id:
        try:
            selected_city = City.objects.get(pk=city_id)
            # 尝试使用已存储的预测
            from django.utils import timezone
            today = timezone.now().date()
            stored_qs = PredictionResult.objects.filter(
                city_id=city_id,
                predict_date__gte=today,
                predict_date__lte=today + timedelta(days=7),
            ).order_by('predict_date')
            if stored_qs.exists():
                stored_predictions = [{
                    'date': str(s.predict_date),
                    'high': s.predicted_high,
                    'low': s.predicted_low,
                    'precip_prob': s.precip_probability,
                    'precip_amount': s.precip_amount,
                } for s in stored_qs]
                stored_accuracy = stored_qs.first().model_accuracy
                stored_model = stored_qs.first().model_name

            # 实时 ML 预测（始终生成，用于多模型对比图）
            predictor = get_predictor(int(city_id))
            all_predictions = predictor.predict_all(int(city_id), days_ahead=7)
            accuracies = predictor.get_all_accuracies()
            best_model_name = predictor.get_best_model()
            recent_data = list(
                WeatherData.objects.filter(city_id=city_id)
                .order_by('-date')[:14]
                .values('date', 'temperature_high', 'temperature_low')
            )
            recent_data.reverse()  # 翻转回升序，图表从左到右按时间
            # 获取未来3天降水概率预报
            precip_forecast = _fetch_precip_forecast(selected_city)
        except City.DoesNotExist:
            pass

    # 把 dict key 的 predictions 序列化
    predictions_json = {}
    for k, v in all_predictions.items():
        predictions_json[k] = v

    # 全部省份列表（用于省份选择器）
    all_provinces = list(_get_city_options().keys())

    context = {
        'city_tree': city_tree,
        'all_provinces': all_provinces,
        'selected_city': selected_city,
        'selected_city_id': int(city_id) if city_id else None,
        'sel_prov': prov,
        'all_predictions': json.dumps(predictions_json, ensure_ascii=False),
        'accuracies': json.dumps(accuracies, ensure_ascii=False),
        'best_model_name': best_model_name,
        'model_colors': json.dumps({k: v['color'] for k, v in ml_model.MODEL_REGISTRY.items()}, ensure_ascii=False),
        'model_names': json.dumps({k: v['name'] for k, v in ml_model.MODEL_REGISTRY.items()}, ensure_ascii=False),
        'recent_data': json.dumps([{
            'date': str(d['date']),
            'high': d['temperature_high'],
            'low': d['temperature_low']
        } for d in recent_data], ensure_ascii=False),
        'precip_forecast': json.dumps(precip_forecast, ensure_ascii=False) if precip_forecast else None,
        'stored_predictions': json.dumps(stored_predictions, ensure_ascii=False) if stored_predictions else None,
        'stored_accuracy': stored_accuracy if stored_predictions else None,
        'stored_model': stored_model if stored_predictions else None,
    }
    return render(request, 'prediction.html', context)


def api_wordcloud_data(request):
    """API: 获取词云数据"""
    from django.db.models import Count
    conditions = WeatherData.objects.values('weather_condition').annotate(
        count=Count('id')
    ).order_by('-count')[:30]

    data = [{
        'name': c['weather_condition'],
        'value': c['count']
    } for c in conditions]

    return JsonResponse({'data': data})


# 降水相关天气类型
PRECIPITATION_TYPES = [
    '小雨', '中雨', '大雨', '暴雨',
    '阵雨', '雷阵雨',
    '小雪', '中雪', '大雪',
    '阵雪',
    '冻雨', '冰雹', '霰',
    '雨夹雪',
]


def precipitation_analysis(request):
    """降水分析页面"""
    from django.utils import timezone
    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')
    prov = request.GET.get('prov', '')

    city_tree = _get_city_options(prov if prov else None)

    context = {
        'year': year,
        'provinces': list(city_tree.keys()),
        'city_tree': city_tree,
        'sel_city': city_id,
        'sel_prov': prov,
    }
    return render(request, 'precipitation_analysis.html', context)


def api_precipitation_data(request):
    """API: 降水统计数据"""
    from django.utils import timezone
    from django.db.models import Sum, Count, Max, Avg, Q

    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')
    prov = request.GET.get('prov', '')

    qs = WeatherData.objects.filter(date__year=year)
    if city_id:
        qs = qs.filter(city_id=int(city_id))
    if prov:
        qs = qs.filter(city__province=prov)

    # 总览统计
    total_days = qs.count()
    precip_qs = qs.filter(weather_condition__in=PRECIPITATION_TYPES)
    precip_days = precip_qs.count()
    precip_total = precip_qs.aggregate(total=Sum('precipitation'))['total'] or 0
    precip_max = precip_qs.aggregate(m=Max('precipitation'))['m'] or 0
    precip_cities = precip_qs.values('city').distinct().count()

    # 各降水类型统计
    type_stats = []
    for wc in PRECIPITATION_TYPES:
        wc_qs = qs.filter(weather_condition=wc)
        days = wc_qs.count()
        if days == 0:
            continue
        total = wc_qs.aggregate(s=Sum('precipitation'))['s'] or 0
        avg = round(total / days, 1)
        type_stats.append({
            'type': wc,
            'days': days,
            'total_precip': round(total, 1),
            'avg_precip': avg,
        })

    # 非降水天数
    non_precip_days = total_days - precip_days

    # 每日降水明细（最近60天，按日期聚合取均值）
    from django.utils import timezone
    daily_raw = list(
        qs.filter(date__gte=timezone.now().date() - timedelta(days=60))
        .values('date', 'weather_condition')
        .annotate(avg_precip=Avg('precipitation'), city_count=Count('city'))
        .order_by('-date')
    )
    daily = [{
        'date': str(d['date']),
        'weather': d['weather_condition'],
        'precip': round(d['avg_precip'] or 0, 1),
        'cities': d['city_count'],
    } for d in daily_raw]

    return JsonResponse({
        'year': year,
        'overview': {
            'total_days': total_days,
            'precip_days': precip_days,
            'non_precip_days': non_precip_days,
            'precip_total': round(precip_total, 1),
            'precip_max': round(precip_max, 1),
            'precip_cities': precip_cities,
        },
        'type_stats': type_stats,
        'daily': daily,
    })


def api_monthly_by_city(request, city_id):
    """API: 获取指定城市月度数据"""
    from django.utils import timezone
    year = int(request.GET.get('year', timezone.now().year))

    data = WeatherData.objects.filter(city_id=city_id, date__year=year)
    monthly = []
    for m in range(1, 13):
        mdata = data.filter(date__month=m)
        if mdata.exists():
            from django.db.models import Avg
            monthly.append({
                'month': f'{m}月',
                'avg_high': round(mdata.aggregate(Avg('temperature_high'))['temperature_high__avg'] or 0, 1),
                'avg_low': round(mdata.aggregate(Avg('temperature_low'))['temperature_low__avg'] or 0, 1),
                'avg_aqi': round(mdata.aggregate(Avg('aqi'))['aqi__avg'] or 0, 1),
            })

    return JsonResponse({'city_id': city_id, 'data': monthly})


def monthly_precip(request):
    """月度降水统计页面"""
    from django.utils import timezone
    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')
    prov = request.GET.get('prov', '')

    context = {
        'year': year,
        'city_tree': _get_city_options(prov if prov else None),
        'sel_city': city_id,
        'sel_prov': prov,
    }
    return render(request, 'monthly_precip.html', context)


def api_monthly_precip(request):
    """API: 月度降水统计数据"""
    from django.utils import timezone
    from django.db.models import Sum, Count, Avg

    year = int(request.GET.get('year', timezone.now().year))
    city_id = request.GET.get('city_id', '')
    prov = request.GET.get('prov', '')

    qs = WeatherData.objects.filter(date__year=year)
    if city_id:
        qs = qs.filter(city_id=int(city_id))
    if prov:
        qs = qs.filter(city__province=prov)

    # 按月聚合
    monthly = []
    # 非降水天气类型（用于标注0mm天气）
    NON_PRECIP = {'晴', '多云', '阴', '雾', '霾', '沙尘', '晴转多云', '多云转阴'}
    for m in range(1, 13):
        mdata = qs.filter(date__month=m)
        days_count = mdata.count()
        if days_count == 0:
            monthly.append({'month': f'{m}月', 'precip_total': 0, 'precip_days': 0,
                           'days_count': 0, 'daily': []})
            continue
        # 多城市用均值/城，单城市用总量
        precip_total_raw = mdata.aggregate(s=Sum('precipitation'), a=Avg('precipitation'))
        city_count = mdata.values('city').distinct().count()
        precip_total = round(precip_total_raw['a'] or 0, 1) if city_count > 1 else round(precip_total_raw['s'] or 0, 1)
        precip_days = mdata.filter(precipitation__gt=0).values('date').distinct().count()

        # 每日详情按日期聚合
        daily_raw = list(
            mdata.values('date').annotate(
                total_precip=Sum('precipitation'),
                avg_precip=Avg('precipitation'),
                city_count=Count('id'),
            ).order_by('date')
        )
        daily = []
        for d in daily_raw:
            # 多城市用均值（0~30mm），单城市用实际值
            cities = d['city_count']
            if cities > 1:
                p = round(d['avg_precip'] or 0, 1)
            else:
                p = round(d['total_precip'] or 0, 1)

            # 取该日期降水类型的众数（非0mm优先）
            precip_weathers = list(
                mdata.filter(date=d['date'], precipitation__gt=0).values('weather_condition')
                .annotate(n=Count('id')).order_by('-n')[:1]
            )
            if precip_weathers:
                w = precip_weathers[0]['weather_condition']
            else:
                top_w = list(
                    mdata.filter(date=d['date']).values('weather_condition')
                    .annotate(n=Count('id')).order_by('-n')[:1]
                )
                w = top_w[0]['weather_condition'] if top_w else '晴'

            daily.append({
                'date': str(d['date']),
                'weather': w,
                'precip': p,
                'cities': cities,
            })

        monthly.append({
            'month': f'{m}月',
            'precip_total': precip_total,
            'precip_days': precip_days,
            'days_count': days_count,
            'daily': daily,
        })

    return JsonResponse({'year': year, 'monthly': monthly})
