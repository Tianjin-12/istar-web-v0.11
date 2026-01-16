from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User

class EmailCodeBackend(BaseBackend):
    """
    邮箱验证码登录认证后端（预留接口）
    """
    def authenticate(self, request, email=None, code=None, **kwargs):
        # 这里将来实现邮箱验证码登录逻辑
        # 目前返回None，表示不使用此认证方式
        return None
        
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None