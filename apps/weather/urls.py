from django.urls import path
from . import views
from . import management_views

urlpatterns = [
    path('', views.index, name='index'),
    path('city/<int:city_id>/', views.city_detail, name='city_detail'),
    path('api/city/<int:city_id>/', views.api_city_data, name='api_city_data'),
    path('api/map/', views.api_map_data, name='api_map_data'),
    path('api/batch/', views.api_batch_weather, name='api_batch_weather'),
    path('api/yearly/', views.api_yearly_daily, name='api_yearly_daily'),
    # 数据管理 (CRUD)
    path('manage/', management_views.data_center, name='data_center'),
    path('manage/add/', management_views.data_add, name='data_add'),
    path('manage/edit/<int:pk>/', management_views.data_edit, name='data_edit'),
    path('manage/delete/<int:pk>/', management_views.data_delete, name='data_delete'),
    path('manage/batch-delete/', management_views.data_batch_delete, name='data_batch_delete'),
    path('manage/cities/', management_views.city_list, name='city_list'),
    path('manage/cities/add/', management_views.city_add, name='city_add'),
    path('manage/cities/edit/<int:pk>/', management_views.city_edit, name='city_edit'),
    path('manage/cities/delete/<int:pk>/', management_views.city_delete, name='city_delete'),
]
