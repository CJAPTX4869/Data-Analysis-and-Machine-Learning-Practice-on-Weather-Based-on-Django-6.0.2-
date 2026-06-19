from django.db import models


class City(models.Model):
    """城市信息表（支持省/市/区县/镇多级）"""
    LEVEL_CHOICES = [
        ('province', '省级'),
        ('city', '地级市'),
        ('district', '区县级'),
        ('town', '镇级'),
    ]
    name = models.CharField(max_length=50, verbose_name='名称')
    province = models.CharField(max_length=50, default='', verbose_name='所属省份')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='city', verbose_name='行政级别')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children', verbose_name='上级行政区')
    latitude = models.FloatField(default=0, verbose_name='纬度')
    longitude = models.FloatField(default=0, verbose_name='经度')
    is_key = models.BooleanField(default=False, verbose_name='是否重点城市')
    sort_order = models.IntegerField(default=0, verbose_name='排序')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'city'
        verbose_name = '城市'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'province', 'name']

    def __str__(self):
        if self.parent:
            return f'{self.parent.name} - {self.name}'
        return f'{self.province} - {self.name}'


class WeatherData(models.Model):
    """天气数据表"""
    # 天气状况选择
    WEATHER_CHOICES = [
        ('晴', '晴'), ('多云', '多云'), ('阴', '阴'),
        ('小雨', '小雨'), ('中雨', '中雨'), ('大雨', '大雨'), ('暴雨', '暴雨'),
        ('阵雨', '阵雨'), ('雷阵雨', '雷阵雨'),
        ('小雪', '小雪'), ('中雪', '中雪'), ('大雪', '大雪'),
        ('阵雪', '阵雪'),
        ('冻雨', '冻雨'), ('冰雹', '冰雹'), ('霰', '霰'),
        ('雨夹雪', '雨夹雪'),
        ('雾', '雾'), ('霾', '霾'), ('沙尘', '沙尘'),
        ('晴转多云', '晴转多云'), ('多云转阴', '多云转阴'),
    ]

    # 风向选择
    WIND_DIRECTION_CHOICES = [
        ('北风', '北风'), ('东北风', '东北风'), ('东风', '东风'),
        ('东南风', '东南风'), ('南风', '南风'), ('西南风', '西南风'),
        ('西风', '西风'), ('西北风', '西北风'), ('无持续风向', '无持续风向'),
    ]

    # 空气质量等级
    AQI_LEVEL_CHOICES = [
        ('优', '优'), ('良', '良'),
        ('轻度污染', '轻度污染'), ('中度污染', '中度污染'),
        ('重度污染', '重度污染'), ('严重污染', '严重污染'),
    ]

    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='weather_data', verbose_name='城市')
    date = models.DateField(verbose_name='日期')
    temperature_high = models.IntegerField(default=0, verbose_name='最高气温(℃)')
    temperature_low = models.IntegerField(default=0, verbose_name='最低气温(℃)')
    weather_condition = models.CharField(max_length=20, choices=WEATHER_CHOICES, default='晴', verbose_name='天气状况')
    wind_direction = models.CharField(max_length=20, choices=WIND_DIRECTION_CHOICES, default='无持续风向', verbose_name='风向')
    wind_power = models.CharField(max_length=20, default='', verbose_name='风力')
    aqi = models.IntegerField(null=True, blank=True, default=None, verbose_name='空气质量指数')
    aqi_level = models.CharField(max_length=20, choices=AQI_LEVEL_CHOICES, null=True, blank=True, default=None, verbose_name='空气质量等级')
    humidity = models.FloatField(null=True, blank=True, default=None, verbose_name='相对湿度(%)')
    precipitation = models.FloatField(default=0, verbose_name='降水量(mm)')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'weather_data'
        verbose_name = '天气数据'
        verbose_name_plural = verbose_name
        ordering = ['-date']
        indexes = [
            models.Index(fields=['city', 'date']),
            models.Index(fields=['date']),
        ]
        unique_together = ['city', 'date']

    def __str__(self):
        return f'{self.city.name} - {self.date} {self.weather_condition}'


class PredictionResult(models.Model):
    """天气预测结果表"""
    city = models.ForeignKey(City, on_delete=models.CASCADE, related_name='predictions', verbose_name='城市')
    predict_date = models.DateField(verbose_name='预测日期')
    predicted_high = models.FloatField(default=0, verbose_name='预测最高温(℃)')
    predicted_low = models.FloatField(default=0, verbose_name='预测最低温(℃)')
    predicted_condition = models.CharField(max_length=20, default='晴', verbose_name='预测天气状况')
    model_accuracy = models.FloatField(default=0, verbose_name='模型准确度')
    model_name = models.CharField(max_length=50, default='RandomForest', verbose_name='模型名称')
    precip_probability = models.IntegerField(null=True, blank=True, default=None, verbose_name='降水概率(%)')
    precip_amount = models.FloatField(null=True, blank=True, default=None, verbose_name='预计降水量(mm)')
    create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'prediction_result'
        verbose_name = '预测结果'
        verbose_name_plural = verbose_name
        ordering = ['-predict_date']

    def __str__(self):
        return f'{self.city.name} - {self.predict_date} 预测: {self.predicted_high}℃/{self.predicted_low}℃'
