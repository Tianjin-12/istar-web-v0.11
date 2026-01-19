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
RUN curl -fsSL https://mirrors.aliyun.com/nodesource/setup_18.x | bash - \
    && apt-get install -y nodejs

# 复制requirements.txt并安装Python依赖
COPY requirements.txt /app/
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 安装Playwright浏览器
RUN pip install playwright
ENV PLAYWRIGHT_DOWNLOAD_HOST=https://npmmirror.com/mirrors/playwright/
RUN playwright install chromium
RUN playwright install-deps chromium


# 复制项目文件
COPY . /app/

# 复制等待脚本
COPY docker-entrypoint.sh /app/
RUN chmod +x /app/docker-entrypoint.sh

# 暴露端口
EXPOSE 8000

# 启动脚本（只用于独立运行，不用于docker-compose）
CMD ["/app/docker-entrypoint.sh"]