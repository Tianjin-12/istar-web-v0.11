# myproject/apps.py
from django.apps import AppConfig

class MyprojectConfig(AppConfig):
    name = 'myproject'
    default_auto_field = 'django.db.models.BigAutoField'
    def ready(self):
        # 导入dash_apps以确保Dash应用被注册
        try:
            import myproject.myproject.dash_apps
            print("Dash apps imported successfully.")
        except ImportError as e:
            print(f"Failed to import dash_apps: {e}")