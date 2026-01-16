# myproject/myproject/__init__.py
# 这会在Django启动时导入dash_apps
default_app_config = 'myproject.app.MyprojectConfig'
# 这会在Django启动时导入Celery应用
from .celery import app as celery_app

__all__ = ('celery_app',)