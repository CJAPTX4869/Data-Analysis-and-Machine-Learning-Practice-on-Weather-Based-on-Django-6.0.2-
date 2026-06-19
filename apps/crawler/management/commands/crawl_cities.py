"""初始化城市数据"""
from django.core.management.base import BaseCommand
from apps.crawler.spider import WeatherSpider


class Command(BaseCommand):
    help = '初始化全国主要城市数据'

    def handle(self, *args, **options):
        spider = WeatherSpider()
        count = spider.init_cities()
        self.stdout.write(self.style.SUCCESS(f'城市数据初始化完成: {count} 个城市'))
