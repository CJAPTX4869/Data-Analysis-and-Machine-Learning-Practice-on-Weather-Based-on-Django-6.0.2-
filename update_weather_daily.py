"""
天气数据每日自动更新脚本（Cron / 任务计划程序 用）
用法: python update_weather_daily.py

智能缺口检测逻辑已内置在 apps/crawler/apps.py 中：
  - 启动 Django 项目时会自动检测数据缺口并补齐
  - 本脚本用于每日定时刷新今日天气（适用于长时间运行不重启的场景）

Windows 任务计划示例（每隔一天执行）:
  schtasks /create /tn "WeatherDailyUpdate" /tr "python D:/creations/Web/项目复刻/weather_system/update_weather_daily.py" /sc daily /st 08:00

Linux crontab 示例（每隔一天执行）:
  0 8 * * * cd /path/to/weather_system && python update_weather_daily.py
"""
import os
import sys

# 修复 Windows 下退出时 Intel MKL 崩溃（libifcoremd.dll）
os.environ.setdefault('MKL_DISABLE_FAST_MM', '1')

import django
from datetime import datetime

# 设置 Django 环境
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'weather_system.settings')
django.setup()

from django.core.management import call_command

if __name__ == '__main__':
    print(f"=== 天气数据每日更新 [{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ===")
    call_command('fetch_today_weather')
    print("=== 更新完成 ===")
