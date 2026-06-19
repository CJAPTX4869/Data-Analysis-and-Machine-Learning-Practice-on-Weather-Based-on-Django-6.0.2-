# 天气预测数据分析可视化系统

基于 Django + ECharts + scikit-learn 的天气预测数据分析可视化系统。自动从 Open-Meteo 免费 API 采集全国天气数据，覆盖省市县乡四级行政区划（重点武汉、黄石）。支持中国地图温度热力图、多维度数据分析（气温/空气质量/风向/14种降水类型）、四种机器学习模型集成预测未来7天气温、天气词云等功能。配有用户注册登录和数据管理后台。

## 功能

- **全国天气数据自动采集** — Open-Meteo 免费 API，每日自动更新
- **中国地图温度可视化** — ECharts 交互式地图，支持省份/城市筛选
- **多维度数据分析** — 月度气温统计、AQI统计、风力分析、降水分析
- **14种降水类型识别** — 雨/雪/冻雨/冰雹/霰/雨夹雪 全覆盖
- **ML多模型预测** — 线性回归、随机森林、梯度提升、SVR + 集成平均（R² 75%+）
- **降水概率预报** — 未来3天降水概率 + 降水量预报
- **完整行政层级** — 省→市→区/县→镇/乡 四级城市体系

## 快速开始

### 1. 环境要求
- Python 3.12+
- MySQL 8.0+
- Windows / Linux / macOS

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置数据库
```bash
# 复制环境变量模板
cp .env.example .env
# 编辑 .env 填入你的 MySQL 密码
```

### 4. 初始化
```bash
# 创建数据库表
python manage.py migrate

# 初始化城市数据
python manage.py crawl_cities

# 拉取历史天气（示例：2026年6月）
python manage.py fetch_history_weather --start 2026-06-01 --end 2026-06-30 --province 湖北
```

### 5. 启动
```bash
python manage.py runserver
```
浏览器打开 http://127.0.0.1:8000/

启动后约5秒，后台线程自动开始补齐天气数据缺口，之后每24小时自动更新。

## 项目结构

```
weather_system/
├── apps/
│   ├── weather/     # 天气数据模型、视图、工具
│   ├── crawler/     # 数据采集（Open-Meteo API）
│   ├── analysis/    # 数据分析（ML预测、统计）
│   └── users/       # 用户系统
├── weather_system/  # Django 配置
├── templates/       # 前端页面
├── static/          # 静态文件
├── manage.py
└── requirements.txt
```

## 技术栈

- **后端**: Django 4.2+ / MySQL / PyMySQL
- **前端**: Bootstrap 5 / ECharts 5 / 原生 JavaScript
- **机器学习**: scikit-learn (随机森林、梯度提升、SVR、线性回归)
- **数据源**: Open-Meteo 免费天气 API
- **中文分词**: jieba (词云分析)

## 数据说明

所有天气数据来自 [Open-Meteo](https://open-meteo.com/) 免费 API：
- **实时/预报**: Forecast API + Air Quality API
- **历史归档**: Archive API（温度/降水/湿度/风速/天气代码）
- **历史AQI**: Air Quality API（支持历史数据回查）

数据每分钟自动检查，每24小时全量刷新，保证数据真实可靠。

## License

MIT
