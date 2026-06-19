/**
 * 中国地图 GeoJSON 注册
 * 数据来源: https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json
 * 通过 fetch 加载 china.json 并注册到 ECharts
 */
(function() {
    // 同步加载 GeoJSON（页面已包含 china.json 的 AJAX 预加载）
    var xhr = new XMLHttpRequest();
    xhr.open('GET', '/static/js/china.json', false); // 同步请求
    xhr.send();
    if (xhr.status === 200) {
        var geoJson = JSON.parse(xhr.responseText);
        echarts.registerMap('china', geoJson);
        console.log('中国地图 GeoJSON 注册成功');
    } else {
        console.warn('中国地图 GeoJSON 加载失败，使用降级散点图');
    }
})();
