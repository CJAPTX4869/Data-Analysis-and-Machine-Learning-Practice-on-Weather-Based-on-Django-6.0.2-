import threading
import time
from datetime import date, timedelta, datetime

from django.apps import AppConfig
from django.core.management import call_command

_auto_fetch_lock = threading.Lock()

# 检查间隔（秒）：24 小时
CHECK_INTERVAL = 24 * 60 * 60


def _do_gap_check_and_fill():
    """
    执行一次数据缺口检测与补齐（核心逻辑）
    返回: (是否检测到缺口, 补齐天数)
    """
    from apps.weather.models import City, WeatherData
    today = date.today()
    year_2026 = date(2026, 1, 1)

    # 1. 确定检查范围（2026年起，最近30天）
    check_start = max(year_2026, today - timedelta(days=30))

    # 2. 查询该范围内已有数据的日期
    existing_dates = set(
        WeatherData.objects
        .filter(date__gte=check_start, date__lte=today)
        .values_list('date', flat=True)
        .distinct()
    )

    if not existing_dates:
        print(f'[自动更新] 2026年起无任何天气数据，仅拉取今日 ({today})')
        call_command('fetch_today_weather')
        return 1

    # 3. 检测假数据日期（湿度=60 且 AQI=60 = 旧版硬编码假值，需重拉）
    stale_dates = set(
        WeatherData.objects
        .filter(date__gte=check_start, date__lte=today, humidity=60, aqi=60)
        .values_list('date', flat=True)
        .distinct()
    )

    # 4. 计算缺失的日期（含假数据日期）
    all_dates = set()
    d = check_start
    while d <= today:
        all_dates.add(d)
        d += timedelta(days=1)

    missing_dates = sorted((all_dates - existing_dates) | stale_dates)

    if not missing_dates and not stale_dates:
        print(f'[自动更新] 天气数据完整 (2026-01-01 ~ {today}，无缺口)')
        # 预测数据也需要定期刷新
        try:
            from apps.analysis.ml_model import batch_generate_predictions
            pred_count = batch_generate_predictions()
            print(f'[自动更新] 预测已更新: {pred_count} 条')
        except Exception as e:
            print(f'[自动更新] 预测更新失败: {e}')
        return 0

    if stale_dates and not missing_dates:
        print(f'[自动更新] 检测到 {len(stale_dates)} 天旧版假数据（湿度/AQI），需重拉修正')

    # 5. 将待处理日期分组为连续区间
    gaps = []
    gap_start = missing_dates[0]
    gap_end = missing_dates[0]
    for i in range(1, len(missing_dates)):
        if missing_dates[i] == gap_end + timedelta(days=1):
            gap_end = missing_dates[i]
        else:
            gaps.append((gap_start, gap_end))
            gap_start = missing_dates[i]
            gap_end = missing_dates[i]
    gaps.append((gap_start, gap_end))

    total_missing = len(missing_dates)
    stale_info = f'（含 {len(stale_dates)} 天假数据修正）' if stale_dates else ''
    print(f'[自动更新] 检测到 {len(gaps)} 个待处理区间，共 {total_missing} 天{stale_info}')

    # 5. 获取所有省份
    provinces = list(City.objects.exclude(province='').values_list('province', flat=True).distinct())

    # 6. 逐个缺口补齐
    for gs, ge in gaps:
        gap_days = (ge - gs).days
        print(f'[自动更新]   缺口: {gs} ~ {ge} ({gap_days + 1}天)')

        if gap_days == 0 and gs == today:
            # 仅缺今天，用 forecast API
            call_command('fetch_today_weather')
        else:
            # 用 archive API 逐省份补齐
            # 注意: fetch_history_weather 内部每个城市有 0.3s 延迟 + 网络 I/O
            # 网络等待期间 GIL 自动释放，不影响用户访问
            for prov in provinces:
                print(f'[自动更新]     处理省份: {prov}')
                call_command('fetch_history_weather',
                             start=gs.strftime('%Y-%m-%d'),
                             end=ge.strftime('%Y-%m-%d'),
                             province=prov)
                time.sleep(0.5)  # 省份之间短暂让出 CPU，确保用户请求不卡

    print(f'[自动更新] 本轮完成! 已补齐 {total_missing} 天数据缺口')

    # 数据更新后自动重算所有城市7天预测
    try:
        from apps.analysis.ml_model import batch_generate_predictions
        print(f'[自动更新] 正在更新天气预测...')
        pred_count = batch_generate_predictions()
        print(f'[自动更新] 预测已更新: {pred_count} 条')
    except Exception as e:
        print(f'[自动更新] 预测更新失败: {e}')

    return total_missing


def _auto_smart_update():
    """
    后台常驻线程：Django 启动后每 24 小时自动检测并补齐数据缺口
    - 首次延迟 5 秒等服务器就绪，之后每隔 24 小时循环检查
    - 项目一直开着也会自动更新，关了几天再开也会补齐空缺
    - 只处理 2026 年及以后的数据（不动 2025 年数据）
    - 加锁防止并发执行
    """
    if not _auto_fetch_lock.acquire(blocking=False):
        print('[自动更新] 已有更新线程在运行，跳过')
        return

    try:
        time.sleep(5)  # 等 Django 完全初始化
        print('[自动更新] 智能更新线程已启动（每24小时检查一次）')

        round_num = 0
        while True:
            round_num += 1
            now = datetime.now()
            print(f'\n[自动更新] ====== 第 {round_num} 轮检查 [{now.strftime("%Y-%m-%d %H:%M:%S")}] ======')

            try:
                _do_gap_check_and_fill()
            except Exception as e:
                print(f'[自动更新] 本轮检查异常: {e}')

            # 下一轮检查时间
            next_time = datetime.now() + timedelta(seconds=CHECK_INTERVAL)
            print(f'[自动更新] 下次检查: {next_time.strftime("%Y-%m-%d %H:%M")} ({CHECK_INTERVAL // 3600}小时后)')
            time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print(f'[自动更新] 线程异常退出: {e}')
    finally:
        _auto_fetch_lock.release()


class CrawlerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.crawler'
    verbose_name = '数据爬虫'

    def ready(self):
        # 自动更新只在主线程触发（避免 runserver 重载时重复执行）
        import os
        if os.environ.get('RUN_MAIN') != 'true':
            return

        t = threading.Thread(target=_auto_smart_update, daemon=True)
        t.start()
