# mvp/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text='必填。请输入有效的电子邮件地址。')
    
    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 自定义表单字段标签和帮助文本
        self.fields['username'].label = '用户名'
        self.fields['email'].label = '电子邮件'
        self.fields['password1'].label = '密码'
        self.fields['password2'].label = '确认密码'
        
        # 更新帮助文本
        self.fields['username'].help_text = '必填。150个字符以内。只能包含字母、数字和@/./+/-/_字符。'
        self.fields['password1'].help_text = '密码不能与您的其他个人信息太相似，至少包含8个字符，不能是常用密码，不能全是数字。'