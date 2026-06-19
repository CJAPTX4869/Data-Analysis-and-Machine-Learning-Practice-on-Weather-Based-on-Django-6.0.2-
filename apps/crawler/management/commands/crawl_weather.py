"""爬取天气数据（使用模拟数据）"""
from django.core.management.base import BaseCommand
from apps.crawler.spider import WeatherSpider


class Command(BaseCommand):
    help = '爬取/生成所有城市的天气数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--real',
            action='store_true',
            help='尝试爬取真实数据（可能需要较长时间，且可能被反爬）',
        )

    def handle(self, *args, **options):
        use_real = options.get('real', False)
        spider = WeatherSpider()
        total = spider.crawl_all(with_sample_data=not use_real)
        self.stdout.write(self.style.SUCCESS(f'天气数据获取完成，共 {total} 条记录'))
