from django.contrib.auth.signals import (user_logged_in,user_logged_out,user_login_failed)
from django.dispatch import receiver
from django.contrib import messages
 
@receiver(user_logged_in)
def login_message(sender, request, user, **kwargs):
    messages.success(request,f"欢迎回来！{user.username}!,您已经成功登录！来康康有什么好康的",extra_tags="success")
