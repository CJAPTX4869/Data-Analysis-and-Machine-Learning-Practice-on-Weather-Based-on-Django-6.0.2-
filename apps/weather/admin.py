from django.contrib import admin
from .models import City, WeatherData, PredictionResult


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ['name', 'province', 'latitude', 'longitude', 'create_time']
    search_fields = ['name', 'province']
    list_filter = ['province']


@admin.register(WeatherData)
class WeatherDataAdmin(admin.ModelAdmin):
    list_display = ['city', 'date', 'temperature_high', 'temperature_low', 'weather_condition', 'aqi', 'aqi_level']
    search_fields = ['city__name']
    list_filter = ['city__province', 'weather_condition', 'aqi_level', 'date']
    date_hierarchy = 'date'


@admin.register(PredictionResult)
class PredictionResultAdmin(admin.ModelAdmin):
    list_display = ['city', 'predict_date', 'predicted_high', 'predicted_low', 'model_accuracy', 'model_name']
    list_filter = ['city', 'model_name']
