# Backend Dockerfile - Django + Gunicorn
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files at BUILD time.
# Use the development settings (SQLite-capable, no required SECRET_KEY/DATABASE_URL)
# so the build does not need production secrets. Runtime uses production settings.
# DB_ENGINE=sqlite 让 base.py 走开发密钥回退（避免构建期因缺 SECRET_KEY 报错），
# 运行期由 compose 的 environment 覆盖为 postgresql。
ENV DB_ENGINE=sqlite
ENV DJANGO_SETTINGS_MODULE=config.settings.development
RUN python manage.py collectstatic --noinput
ENV DJANGO_SETTINGS_MODULE=config.settings.production

# Run Gunicorn (via entrypoint that migrates first)
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh
ENTRYPOINT ["./docker-entrypoint.sh"]
# PORT is injected by Hugging Face Spaces (default 7860). Bind to 0.0.0.0:$PORT.
#
# ── workers=3 是实测选定的值，不是拍脑袋（2026-10-16）────────────────────
# 生产机器只有 **2 vCPU / 3.5 GB**。用 gunicorn 信号（SIGTTOU/SIGTTIN）做梯度实测，
# search 索引优化后的新基线（容器内直连，每线程 40 请求，全档位错误率 0%）：
#
#   workers | c=5 QPS | c=5 p95 | c=5 p99 | c=20 QPS | c=20 p95 | c=20 p99
#   --------+---------+---------+---------+----------+----------+---------
#      5    |  15.5   |  939ms  | 1104ms  |  16.4    |  2954ms  |  3856ms
#      4    |  16.3   |  726ms  | 1026ms  |  16.2    |  2540ms  |  3395ms
#   > 3<    |  16.8   |  691ms  |  916ms  |  16.4    |  2570ms  |  2966ms
#      2    |  16.0   |  756ms  |  997ms  |  16.7    |  2105ms  |  2702ms
#
# 结论：workers=5 是**延迟最差**的配置（p95 939ms，比 workers=3 高 36%）；
# worker 越多，每个进程各自的 Django 初始化/ORM 元数据/连接池副本越占内存
# （实测每 worker 约 130 MB RSS，5 个= 650 MB），2 核机器上进程切换与
# cache 争抢反而拉高尾延迟。workers=3 在中低并发（真实场景）p95/p99 最优，
# 且留有 1 个余量槽应对突发。
#
# ⚠️ 升级机器（≥4 vCPU）后应重新做同样的梯度实测再调，本注释的数字只对
#    2 vCPU 机器成立。
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --threads 4 --worker-class gthread --timeout 120"]
