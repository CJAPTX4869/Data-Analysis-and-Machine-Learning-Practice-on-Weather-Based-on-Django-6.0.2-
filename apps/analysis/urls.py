from django.urls import path
from . import views

urlpatterns = [
    path('monthly/', views.monthly_stats, name='monthly_stats'),
    path('aqi/', views.aqi_stats, name='aqi_stats'),
    path('wind/', views.wind_analysis, name='wind_analysis'),
    path('wordcloud/', views.wordcloud_view, name='wordcloud'),
    path('prediction/', views.prediction, name='prediction'),
    path('precipitation/', views.precipitation_analysis, name='precipitation_analysis'),
    path('api/wordcloud/', views.api_wordcloud_data, name='api_wordcloud_data'),
    path('api/monthly/<int:city_id>/', views.api_monthly_by_city, name='api_monthly_by_city'),
    path('api/precipitation/', views.api_precipitation_data, name='api_precipitation_data'),
    path('precipitation/monthly/', views.monthly_precip, name='monthly_precip'),
    path('api/precipitation/monthly/', views.api_monthly_precip, name='api_monthly_precip'),
]
