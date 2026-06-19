/**
 * 天气预测数据分析可视化系统 - 全局脚本
 */

// CSRF Token 设置 (Django)
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

// jQuery AJAX 全局设置 CSRF
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!(/^http:.*/.test(settings.url) || /^https:.*/.test(settings.url))) {
            xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
    }
});

// ECharts 通用主题配置
const chartTheme = {
    color: ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4'],
    textStyle: {
        fontFamily: 'Microsoft YaHei, PingFang SC, sans-serif'
    }
};

// 初始化图表 (响应式)
function initChart(domId) {
    const dom = document.getElementById(domId);
    if (!dom) return null;
    const chart = echarts.init(dom);
    // 响应式
    window.addEventListener('resize', () => chart.resize());
    return chart;
}

// 通用图表配置
function getCommonOption() {
    return {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' }
        },
        toolbox: {
            feature: {
                saveAsImage: { title: '保存图片' },
                dataView: { title: '数据视图', readOnly: true },
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true
        }
    };
}

// 数字动画
function animateValue(element, start, end, duration) {
    const range = end - start;
    const increment = range / (duration / 16);
    let current = start;
    const timer = setInterval(() => {
        current += increment;
        if ((increment > 0 && current >= end) || (increment < 0 && current <= end)) {
            current = end;
            clearInterval(timer);
        }
        element.textContent = Math.round(current).toLocaleString();
    }, 16);
}

// 日期格式化
function formatDate(dateStr) {
    const d = new Date(dateStr);
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

// Toast提示
function showToast(message, type = 'info') {
    const colors = {
        success: '#198754',
        error: '#dc3545',
        warning: '#ffc107',
        info: '#0dcaf0'
    };
    const container = document.createElement('div');
    container.style.cssText = `
        position: fixed; top: 80px; right: 20px; z-index: 9999;
        background: ${colors[type] || colors.info}; color: #fff;
        padding: 12px 24px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        transition: all 0.3s; opacity: 1;
    `;
    container.textContent = message;
    document.body.appendChild(container);
    setTimeout(() => {
        container.style.opacity = '0';
        setTimeout(() => container.remove(), 300);
    }, 3000);
}

console.log('天气预测数据分析可视化系统 - 已加载');
