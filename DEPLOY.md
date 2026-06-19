# 天气预测数据分析可视化系统 — 部署与运维文档

> 域名: `mihayou.icu` | 服务器: 阿里云 CentOS Stream 9 | 2GB RAM + 40GB SSD × 2台  
> 工具: MobaXterm | 架构: Web服务器 + 数据库服务器 分离部署

---

## 一、服务器架构

```
┌──────────────────────┐     ┌──────────────────────┐
│   服务器A (Web)       │────▶│   服务器B (DB)         │
│   公网IP: X.X.X.X    │3306 │   内网IP: 10.x.x.x    │
│                      │     │                      │
│   Nginx :80/443      │     │   MySQL 8.0 :3306    │
│   Gunicorn :8000     │     │                      │
│   Django 项目代码     │     │   天气数据库          │
│   静态文件            │     │                      │
│   Cron 定时任务       │     │   Cron 备份任务       │
└──────────────────────┘     └──────────────────────┘
```

---

## 二、服务器初始化（两台都要做）

### 2.1 用 MobaXterm 连接

1. 打开 MobaXterm → Session → SSH
2. Remote host: 输入阿里云公网IP
3. Username: `root`
4. Port: `22`
5. 点击 OK，输入密码

### 2.2 基础配置

```bash
# === 两台服务器都执行 ===

# 1. 更新系统
dnf update -y

# 2. 安装基础工具
dnf install -y vim wget curl git net-tools telnet tar gzip unzip

# 3. 关闭 SELinux
setenforce 0
sed -i 's/SELINUX=enforcing/SELINUX=disabled/' /etc/selinux/config

# 4. 防火墙放行端口
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=443/tcp
firewall-cmd --permanent --add-port=8000/tcp
firewall-cmd --reload

# 5. 设置时区
timedatectl set-timezone Asia/Shanghai

# 6. 创建部署用户（可选）
useradd -m -s /bin/bash deploy
echo 'deploy:YourPassword123!' | chpasswd
usermod -aG wheel deploy
```

### 2.3 阿里云安全组配置

登录阿里云控制台 → 云服务器ECS → 安全组 → 配置规则 → 入方向添加:

| 端口 | 来源 | 说明 |
|------|------|------|
| 22 | 0.0.0.0/0 | SSH |
| 80 | 0.0.0.0/0 | HTTP |
| 443 | 0.0.0.0/0 | HTTPS |
| 3306 | 服务器A的内网IP/32 | MySQL(仅允许Web服务器访问) |

---

## 三、服务器B — 数据库服务器

### 3.1 安装 MySQL 8.0

```bash
# === 只在服务器B执行 ===

# 安装 MySQL
dnf install -y mysql-server

# 启动并设置开机自启
systemctl start mysqld
systemctl enable mysqld

# 安全初始化
mysql_secure_installation
# 按提示操作:
#   VALIDATE PASSWORD: n (简单密码)
#   New password: WeatherDb@2026!
#   Remove anonymous users: y
#   Disallow root remote login: n (我们需要远程连接)
#   Remove test database: y
#   Reload privilege tables: y
```

### 3.2 创建数据库和用户

```bash
mysql -u root -p
```

```sql
-- 创建数据库
CREATE DATABASE weather_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 创建远程用户（允许Web服务器连接）
CREATE USER 'weather'@'%' IDENTIFIED BY 'WeatherApp@2026!';
GRANT ALL PRIVILEGES ON weather_system.* TO 'weather'@'%';
FLUSH PRIVILEGES;

-- 验证
SELECT user, host FROM mysql.user WHERE user = 'weather';
EXIT;
```

### 3.3 允许远程连接

```bash
# 编辑MySQL配置
vim /etc/my.cnf.d/mysql-server.cnf
```

在 `[mysqld]` 段添加:
```ini
bind-address = 0.0.0.0
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci
max_connections = 200
```

```bash
# 重启MySQL
systemctl restart mysqld
```

---

## 四、服务器A — Web服务器

### 4.1 安装 Python 3.11+

```bash
# === 只在服务器A执行 ===

# CentOS Stream 9 自带 Python 3.9，升级到 3.11
dnf install -y python3.11 python3.11-devel python3.11-pip

# 设置默认
alternatives --set python3 /usr/bin/python3.11
python3 --version  # 确认 3.11.x

# 创建虚拟环境目录
mkdir -p /opt/venvs
python3 -m venv /opt/venvs/weather
```

### 4.2 安装 Nginx

```bash
dnf install -y nginx
systemctl start nginx
systemctl enable nginx
# 浏览器访问 http://服务器A公网IP 应看到 Nginx 欢迎页
```

### 4.3 上传项目代码

在 **MobaXterm** 左侧文件浏览器中，将本地 `weather_system` 文件夹拖到 `/opt/` 目录

或者用 scp:
```bash
# 在本地 Windows PowerShell 中执行
scp -r D:\creations\Web\项目复刻\weather_system root@服务器A公网IP:/opt/
```

### 4.4 安装 Python 依赖

```bash
cd /opt/weather_system
source /opt/venvs/weather/bin/activate

# 升级 pip
pip install --upgrade pip

# 安装依赖
pip install -r requirements.txt

# 额外安装生产环境依赖
pip install gunicorn
```

### 4.5 修改 Django 配置

```bash
# 创建生产环境配置文件
cp weather_system/settings.py weather_system/settings_prod.py
vim weather_system/settings_prod.py
```

修改以下内容:
```python
# settings_prod.py 关键修改

import os
from .settings import *

DEBUG = False
ALLOWED_HOSTS = ['mihayou.icu', 'www.mihayou.icu', '服务器A公网IP']

# 数据库连接指向服务器B（内网IP）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'weather_system',
        'USER': 'weather',
        'PASSWORD': 'WeatherApp@2026!',
        'HOST': '10.x.x.x',  # 服务器B的内网IP
        'PORT': '3306',
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

STATIC_ROOT = '/opt/weather_system/staticfiles'
MEDIA_ROOT = '/opt/weather_system/media'

# 安全设置
SECRET_KEY = '替换为一个长的随机字符串'
CSRF_CODED_ORIGINS = ['https://mihayou.icu', 'https://www.mihayou.icu']
SECURE_SSL_REDIRECT = False  # Nginx处理SSL
```

生成 SECRET_KEY:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 4.6 初始化数据库

```bash
cd /opt/weather_system
source /opt/venvs/weather/bin/activate

# 设置生产环境
export DJANGO_SETTINGS_MODULE=weather_system.settings_prod

# 先测试数据库连接
python manage.py check --settings=weather_system.settings_prod

# 迁移数据库
python manage.py migrate --settings=weather_system.settings_prod

# 创建超级用户
python manage.py createsuperuser --settings=weather_system.settings_prod
# 用户名: admin
# 邮箱: admin@mihayou.icu
# 密码: WeatherAdmin@2026!

# 初始化城市数据
python manage.py crawl_cities --settings=weather_system.settings_prod

# 生成历史天气数据（模拟数据，快速）
python manage.py crawl_weather --settings=weather_system.settings_prod

# 获取今日真实天气（通过API，约5分钟）
python manage.py fetch_today_weather --settings=weather_system.settings_prod

# 收集静态文件
python manage.py collectstatic --settings=weather_system.settings_prod --noinput
```

### 4.7 配置 Gunicorn

```bash
# 创建 systemd 服务文件
vim /etc/systemd/system/gunicorn.service
```

```ini
[Unit]
Description=Weather System Gunicorn
After=network.target

[Service]
User=root
Group=root
WorkingDirectory=/opt/weather_system
Environment="DJANGO_SETTINGS_MODULE=weather_system.settings_prod"
ExecStart=/opt/venvs/weather/bin/gunicorn weather_system.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 3 \
    --threads 2 \
    --timeout 120 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
# 创建日志目录
mkdir -p /var/log/gunicorn

# 启动 Gunicorn
systemctl daemon-reload
systemctl start gunicorn
systemctl enable gunicorn

# 检查状态
systemctl status gunicorn
# 确认 Active: active (running)
```

### 4.8 配置 Nginx

```bash
vim /etc/nginx/conf.d/weather.conf
```

```nginx
# HTTP → 先配置 HTTP，等证书下来再加 HTTPS
server {
    listen 80;
    server_name mihayou.icu www.mihayou.icu;

    # 静态文件
    location /static/ {
        alias /opt/weather_system/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /opt/weather_system/media/;
        expires 7d;
    }

    # 代理到 Gunicorn
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
    }

    # Gzip
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript;
    gzip_min_length 1000;
}
```

```bash
# 测试配置
nginx -t

# 重载
systemctl reload nginx
```

---

## 五、域名和 SSL 配置

### 5.1 DNS 解析（在域名服务商处操作）

登录 `mihayou.icu` 域名管理后台，添加 A 记录:

| 类型 | 主机记录 | 记录值 |
|------|----------|--------|
| A | @ | 服务器A公网IP |
| A | www | 服务器A公网IP |

### 5.2 安装 Certbot 获取 SSL

```bash
# === 服务器A ===

# DNS生效后安装 certbot
dnf install -y epel-release
dnf install -y certbot python3-certbot-nginx

# 获取证书
certbot --nginx -d mihayou.icu -d www.mihayou.icu
# 输入邮箱: admin@mihayou.icu
# 同意条款: y
# 是否重定向HTTP到HTTPS: 2 (自动重定向)

# 测试自动续期
certbot renew --dry-run
```

### 5.3 最终 Nginx 配置（certbot会自动修改）

检查 `/etc/nginx/conf.d/weather.conf`，certbot 已自动添加 SSL 配置。

```bash
nginx -t && systemctl reload nginx
```

---

## 六、定时任务（Cron）

### 6.1 每日天气更新

```bash
# === 服务器A ===

# 创建更新脚本
vim /opt/weather_system/update_daily.sh
```

```bash
#!/bin/bash
# 每日天气数据更新脚本
set -e

LOG_FILE="/var/log/weather_update.log"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') 开始每日更新 ===" >> $LOG_FILE

cd /opt/weather_system
source /opt/venvs/weather/bin/activate
export DJANGO_SETTINGS_MODULE=weather_system.settings_prod

# 更新今日天气
python manage.py fetch_today_weather 2>&1 | tail -5 >> $LOG_FILE

# 每周末拉取历史数据补齐
if [ $(date +%u) -eq 7 ]; then
    echo "周末补齐历史数据..." >> $LOG_FILE
    END_DATE=$(date +%Y-%m-%d)
    python manage.py fetch_history_weather --end $END_DATE --province 湖北 2>&1 | tail -3 >> $LOG_FILE
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 更新完成 ===" >> $LOG_FILE
```

```bash
chmod +x /opt/weather_system/update_daily.sh

# 添加 cron 任务（每天早上8点）
crontab -e
```

```
# 每天8:00更新天气
0 8 * * * /opt/weather_system/update_daily.sh

# 每天凌晨2点清理旧日志
0 2 * * * find /var/log/gunicorn -name "*.log" -mtime +30 -delete
```

### 6.2 数据库备份（服务器B）

```bash
# === 服务器B ===

vim /opt/db_backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups"
mkdir -p $BACKUP_DIR

DATE=$(date +%Y%m%d_%H%M)
mysqldump -u root -p'WeatherDb@2026!' --databases weather_system \
    | gzip > $BACKUP_DIR/weather_$DATE.sql.gz

# 保留最近7天
find $BACKUP_DIR -name "weather_*.sql.gz" -mtime +7 -delete

echo "$(date): Backup completed, size: $(du -h $BACKUP_DIR/weather_$DATE.sql.gz | cut -f1)" >> /var/log/db_backup.log
```

```bash
chmod +x /opt/db_backup.sh

# 每天凌晨3点备份
crontab -e
```

```
0 3 * * * /opt/db_backup.sh
```

---

## 七、运维命令速查

### 7.1 服务管理

```bash
# === 服务器A ===

# 查看所有服务状态
systemctl status nginx gunicorn

# 重启服务
systemctl restart gunicorn
systemctl reload nginx

# 查看日志
tail -f /var/log/gunicorn/error.log
tail -f /var/log/nginx/error.log
journalctl -u gunicorn -f

# 进入Django环境
cd /opt/weather_system
source /opt/venvs/weather/bin/activate
export DJANGO_SETTINGS_MODULE=weather_system.settings_prod
python manage.py shell
```

### 7.2 更新代码

```bash
# === 服务器A ===

# 1. 上传新代码（MobaXterm拖拽或scp）
# 2. 进入项目目录
cd /opt/weather_system
source /opt/venvs/weather/bin/activate

# 3. 数据库迁移（如果有model变更）
python manage.py migrate --settings=weather_system.settings_prod

# 4. 更新静态文件
python manage.py collectstatic --settings=weather_system.settings_prod --noinput

# 5. 重启服务
systemctl restart gunicorn
```

### 7.3 手动更新天气数据

```bash
# === 服务器A ===
cd /opt/weather_system
source /opt/venvs/weather/bin/activate
export DJANGO_SETTINGS_MODULE=weather_system.settings_prod

# 更新今日天气
python manage.py fetch_today_weather

# 更新指定省份
python manage.py fetch_today_weather --province 湖北

# 拉取历史数据（某段时间）
python manage.py fetch_history_weather --start 2026-01-01 --end 2026-06-05 --province 湖北
```

### 7.4 数据库维护（服务器B）

```bash
# === 服务器B ===

# 连接数据库
mysql -u root -p

# 查看数据统计
USE weather_system;
SELECT COUNT(*) FROM weather_data;
SELECT COUNT(*) FROM city;
SELECT province, COUNT(*) FROM city WHERE level='city' GROUP BY province;

# 手动备份
mysqldump -u root -p'WeatherDb@2026!' weather_system | gzip > /opt/weather_backup_$(date +%Y%m%d).sql.gz

# 恢复备份
gunzip < /opt/backups/weather_20260606_0300.sql.gz | mysql -u root -p'WeatherDb@2026!' weather_system
```

### 7.5 监控

```bash
# === 服务器A ===

# 磁盘使用
df -h

# 内存使用
free -h

# 进程
ps aux | grep gunicorn
ps aux | grep nginx

# 网络连接
ss -tlnp | grep -E '80|443|8000'

# 访问日志
tail -100 /var/log/nginx/access.log

# 实时访问量
tail -f /var/log/nginx/access.log | grep "$(date +%d/%b/%Y)"
```

---

## 八、故障排查

| 问题 | 检查 |
|------|------|
| 502 Bad Gateway | `systemctl status gunicorn` → 查看是否crash |
| 数据库连接失败 | 服务器A `telnet 服务器B内网IP 3306` → 检查安全组 |
| 静态文件404 | 确认 `collectstatic` 已执行，Nginx `/static/` 路径正确 |
| SSL证书过期 | `certbot renew --dry-run` 测试 |
| 内存不足 | `gunicorn` workers数改为2 |
| 天气数据不更新 | `crontab -l` 检查定时任务, `/var/log/weather_update.log` 查看日志 |

### 内存优化（2GB RAM）

```bash
# gunicorn配置中 workers=3, threads=2 约占用 600MB
# MySQL 配置优化 (服务器B /etc/my.cnf.d/mysql-server.cnf)
[mysqld]
innodb_buffer_pool_size = 512M
key_buffer_size = 64M
max_connections = 100
```

---

## 九、检查清单

部署完成后逐项验证：

- [ ] `http://mihayou.icu` → 自动跳转 `https://mihayou.icu`
- [ ] 首页正常显示中国地图和城市列表
- [ ] 点击城市进入详情页，图表正常渲染
- [ ] 登录 `admin / WeatherAdmin@2026!` 成功
- [ ] `/manage/` 数据管理页面可搜索编辑
- [ ] `/admin/` Django后台可以访问
- [ ] `https://mihayou.icu/admin/` SSL绿色锁
- [ ] 手机访问响应式正常
- [ ] `certbot renew --dry-run` 成功
- [ ] 服务器A重启后 `systemctl status gunicorn nginx` 均 active
- [ ] 定时任务 `crontab -l` 已配置
- [ ] 服务器B数据库备份脚本可执行

---

> 📧 技术支持: admin@mihayou.icu  
> 📅 最后更新: 2026-06-06
