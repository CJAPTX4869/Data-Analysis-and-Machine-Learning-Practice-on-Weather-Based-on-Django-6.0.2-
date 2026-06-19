"""天气数据管理表单 - ModelForm"""
from django import forms
from .models import City, WeatherData


class WeatherDataForm(forms.ModelForm):
    class Meta:
        model = WeatherData
        fields = ['city', 'date', 'temperature_high', 'temperature_low',
                  'weather_condition', 'wind_direction', 'wind_power',
                  'aqi', 'aqi_level', 'humidity', 'precipitation']
        widgets = {
            'city': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'date': forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'temperature_high': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '℃'}),
            'temperature_low': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '℃'}),
            'weather_condition': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'wind_direction': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'wind_power': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '如: 3-4级'}),
            'aqi': forms.NumberInput(attrs={'class': 'form-control form-control-sm'}),
            'aqi_level': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'humidity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': '%'}),
            'precipitation': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'mm'}),
        }


class CityForm(forms.ModelForm):
    class Meta:
        model = City
        fields = ['name', 'province', 'level', 'parent', 'latitude', 'longitude', 'is_key']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'province': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'level': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'parent': forms.Select(attrs={'class': 'form-control form-control-sm'}),
            'latitude': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'longitude': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
            'is_key': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SearchForm(forms.Form):
    """搜索表单 - 按省份/城市/天气/日期分类搜索"""
    province = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-sm', 'placeholder': '省份: 广东/湖北...'
    }))
    city = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-sm', 'placeholder': '城市名'
    }))
    weather = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'class': 'form-control form-control-sm', 'placeholder': '晴/雨/多云...'
    }))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'class': 'form-control form-control-sm', 'type': 'date', 'placeholder': '开始'
    }))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'class': 'form-control form-control-sm', 'type': 'date', 'placeholder': '结束'
    }))
