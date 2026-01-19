#!/bin/sh
set -e

# 等待数据库就绪
echo "等待数据库就绪..."
until python -c "
import os
import psycopg2
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
import django
django.setup()
from django.db import connection
connection.ensure_connection()
print('数据库连接成功')
"; do
  echo "数据库尚未就绪，等待5秒..."
  sleep 5
done

# 执行数据库迁移
echo "执行数据库迁移..."
python myproject/manage.py migrate --noinput

echo "Django 初始化完成"
