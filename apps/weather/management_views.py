"""数据管理中心视图 - 登录后可增删改查"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from .models import City, WeatherData
from .forms import WeatherDataForm, CityForm, SearchForm


@login_required
def data_center(request):
    """数据管理中心首页 - 天气数据列表"""
    search = SearchForm(request.GET)
    qs = WeatherData.objects.select_related('city').all()

    if search.is_valid():
        prov = search.cleaned_data.get('province')
        city = search.cleaned_data.get('city')
        weather = search.cleaned_data.get('weather')
        df = search.cleaned_data.get('date_from')
        dt = search.cleaned_data.get('date_to')
        if prov:
            qs = qs.filter(city__province__icontains=prov)
        if city:
            qs = qs.filter(city__name__icontains=city)
        if weather:
            qs = qs.filter(weather_condition__icontains=weather)
        if df:
            qs = qs.filter(date__gte=df)
        if dt:
            qs = qs.filter(date__lte=dt)

    qs = qs.order_by('-date', 'city__name')
    paginator = Paginator(qs, 25)
    page = request.GET.get('page', 1)
    records = paginator.get_page(page)

    # 构建查询字符串（保留搜索参数给分页用）
    query_string = request.GET.copy()
    if 'page' in query_string:
        del query_string['page']

    # 省份列表（按城市数排序）
    provinces = City.objects.filter(level='city').values('province').distinct().order_by('province')

    return render(request, 'manage/data_list.html', {
        'records': records, 'search': search,
        'total': qs.count(), 'query_string': query_string.urlencode(),
        'provinces': provinces,
    })


@login_required
def data_add(request):
    """新增天气记录"""
    if request.method == 'POST':
        form = WeatherDataForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'新增成功: {obj.city.name} {obj.date}')
            return redirect('data_center')
    else:
        form = WeatherDataForm()
    return render(request, 'manage/data_form.html', {'form': form, 'action': '新增'})


@login_required
def data_edit(request, pk):
    """编辑天气记录"""
    obj = get_object_or_404(WeatherData, pk=pk)
    if request.method == 'POST':
        form = WeatherDataForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'更新成功: {obj.city.name} {obj.date}')
            return redirect('data_center')
    else:
        form = WeatherDataForm(instance=obj)
    return render(request, 'manage/data_form.html', {'form': form, 'action': '编辑', 'obj': obj})


@login_required
def data_delete(request, pk):
    """删除天气记录"""
    obj = get_object_or_404(WeatherData, pk=pk)
    if request.method == 'POST':
        info = f'{obj.city.name} {obj.date}'
        obj.delete()
        messages.success(request, f'已删除: {info}')
        return redirect('data_center')
    return render(request, 'manage/confirm_delete.html', {'obj': obj, 'type': '天气记录'})


@login_required
def city_list(request):
    """城市管理列表"""
    cities = City.objects.select_related('parent').all().order_by('province', 'sort_order')
    # 统计每个城市的数据量
    from django.db.models import Count
    cities = cities.annotate(data_count=Count('weather_data'))
    return render(request, 'manage/city_list.html', {'cities': cities})


@login_required
def city_add(request):
    """新增城市"""
    if request.method == 'POST':
        form = CityForm(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, f'城市新增成功: {obj.name}')
            return redirect('city_list')
    else:
        form = CityForm()
    return render(request, 'manage/data_form.html', {'form': form, 'action': '新增城市'})


@login_required
def city_edit(request, pk):
    """编辑城市"""
    obj = get_object_or_404(City, pk=pk)
    if request.method == 'POST':
        form = CityForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'城市更新成功: {obj.name}')
            return redirect('city_list')
    else:
        form = CityForm(instance=obj)
    return render(request, 'manage/data_form.html', {'form': form, 'action': '编辑城市', 'obj': obj})


@login_required
def city_delete(request, pk):
    """删除城市"""
    obj = get_object_or_404(City, pk=pk)
    if request.method == 'POST':
        info = obj.name
        obj.delete()
        messages.success(request, f'已删除城市: {info}')
        return redirect('city_list')
    return render(request, 'manage/confirm_delete.html', {'obj': obj, 'type': '城市'})


@login_required
def data_batch_delete(request):
    """批量删除"""
    if request.method == 'POST':
        ids = request.POST.getlist('ids')
        if ids:
            cnt, _ = WeatherData.objects.filter(id__in=ids).delete()
            messages.success(request, f'批量删除 {cnt} 条记录')
    return redirect('data_center')
