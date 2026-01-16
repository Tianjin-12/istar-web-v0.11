# 使用Python 3.12作为基础镜像
FROM python:3.12-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        build-essential \
        curl \
        gnupg \
        && rm -rf /var/lib/apt/lists/*

# 安装Node.js (Dash需要)
RUN curl -fsSL https://mirrors.aliyun.com/nodejs/release_18.x | bash - \
    && apt-get install -y nodejs

# 复制requirements.txt并安装Python依赖
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 安装Playwright浏览器
RUN playwright install chromium
RUN playwright install-deps

# 复制项目文件
COPY . /app/

# 创建staticfiles目录
RUN mkdir -p /app/staticfiles

# 收集静态文件
RUN python /app/myproject/manage.py collectstatic --noinput

# 暴露端口
EXPOSE 8000

# 启动脚本
CMD ["sh", "-c", "python /app/myproject/manage.py migrate && gunicorn --bind 0.0.0.0:8000 myproject.wsgi:application"]