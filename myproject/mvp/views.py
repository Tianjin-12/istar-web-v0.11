from django_plotly_dash.models import StatelessApp
from django_plotly_dash.util import serve_locally
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets
from .models import Mention_percentage
from .serializers import Mention_percentageSerializer
import json
from django.utils.dateparse import parse_datetime
from django.db.models import Avg
from rest_framework.response import Response
from datetime import datetime, timedelta
from django.core.cache import cache
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Order
from .tasks import process_order, send_notification
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.urls import reverse_lazy
from django.views.generic.edit import CreateView
from .forms import CustomUserCreationForm 
from django.contrib.auth.forms import AuthenticationForm
from functools import wraps
from urllib.parse import urlparse, urlencode
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.shortcuts import resolve_url
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods



def login_required_new_tab(function=None, redirect_field_name=REDIRECT_FIELD_NAME, login_url=None):
    """
    自定义的login_required装饰器，当用户未登录时在新标签页中打开登录页面
    登录成功后自动刷新原始页面
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapper_view(request, *args, **kwargs):
            if request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
            
            # 用户未登录，返回一个在新标签页中打开登录页面的响应
            path = request.build_absolute_uri()
            resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)
            
            # 构建带有next参数的登录URL
            query_params = {redirect_field_name: path}
            login_url_with_next = f"{resolved_login_url}?{urlencode(query_params)}"
            
            # 返回一个包含JavaScript的响应，在新标签页中打开登录页面并监听登录状态
            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Redirecting to Login</title>
            </head>
            <body>
                <script>
                    // 打开登录页面
                    var loginWindow = window.open('{login_url_with_next}', '_blank');
                    // 定期检查登录窗口是否关闭
                    var checkInterval = setInterval(function() {{
                        if (loginWindow.closed) {{
                            clearInterval(checkInterval);
                            // 检查用户是否已登录
                            fetch('/api/check-auth/')
                                .then(response => response.json())
                                .then(data => {{
                                    if (data.authenticated) {{
                                        window.location.reload();
                                    }}
                                }})
                                .catch(error => {{
                                    console.error('Error checking auth status:', error);
                                }});
                        }}
                    }}, 1000);
                </script>
            </body>
            </html>
            """
            return HttpResponse(html)
        return _wrapper_view
    if function:
        return decorator(function)
    return decorator

@csrf_exempt
def logout_view(request):
    """处理退出登录请求"""
    from django.contrib.auth import logout
    logout(request)
    return JsonResponse({'success': True})

@csrf_exempt
def auth_check(request):
    if request.user.is_authenticated:
        return JsonResponse({
            'authenticated': True,
            'username': request.user.username,
            'email': request.user.email
        })
    else:
        return JsonResponse({
            'authenticated': False,
            'username': None,
            'email': None
        })



class RegisteringView(CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'registration/register.html'
    success_url = '/'  # 注册成功后重定向的URL
    
    def form_valid(self, form):
        # 调用父类的form_valid方法创建用户
        response = super().form_valid(form)
        # 自动登录新注册的用户
        login(self.request, self.object)
        return response
    
    def form_invalid(self, form):
        # 添加调试信息
        print("表单验证失败:", form.errors)
        return super().form_invalid(form)
    
@login_required_new_tab
def order_list(request):
    """显示所有订单的列表"""
    orders = Order.objects.all().order_by('-created_at')
    return render(request, 'mvp/order_list.html', {'orders': orders})

@login_required_new_tab
def create_order(request):
    """创建新订单"""
    if request.method == 'POST':
        keyword = request.POST.get('keyword')
        brand = request.POST.get('brand') 
        if keyword and brand:
            # 创建订单
            order = Order.objects.create(
                user=request.user,
                keyword=keyword,
                brand=brand,
                status='pending')
            # 启动异步任务处理订单
            task = process_order.delay(order.id)
            order.task_id = task.id
            order.save()
            messages.success(request, f"订单 {order.id} 已创建，正在处理中...")
        else:
            messages.error(request, "请提供关键词和品牌词")
    # 获取预填的品牌和关键词（如果有）
    prefilled_brand = request.session.pop('prefilled_brand', '')
    prefilled_keyword = request.session.pop('prefilled_keyword', '')
    return render(request, 'mvp/create_order.html', {
        'prefilled_brand': prefilled_brand,
        'prefilled_keyword': prefilled_keyword
    })


@login_required_new_tab
@require_POST
def toggle_light(request, order_id):
    """
    切换订单的灯泡状态
    """
    try:
        order = Order.objects.get(id=order_id, user=request.user)
        
        if order.light_status:
            # 灯泡亮着，点击后熄灭
            order.light_status = False
            order.light_clicks -= 1
            message = f"订单 #{order.id} 的灯泡已熄灭"
        else:
            # 灯泡熄灭，点击后点亮
            order.light_status = True
            order.light_clicks += 1
            message = f"订单 #{order.id} 的灯泡已点亮"
            
        order.save()
        
        # 发送通知
        send_notification(
            user_id=request.user.id,
            message=message,
            notification_type='light_toggle'
        )
        
        return JsonResponse({
            'success': True,
            'light_status': order.light_status,
            'light_clicks': order.light_clicks,
            'message': message
        })
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': '订单不存在'})
class Mention_percentageViewSet(viewsets.ModelViewSet):
    """品牌提及百分比API视图集"""
    queryset = Mention_percentage.objects.all()
    serializer_class = Mention_percentageSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)
        return queryset
    
# API端点，用于获取仪表盘数据
@csrf_exempt
def dashboard_data_api(request):
    if request.method == 'GET':
        try:
            brand_name = request.GET.get('brand_name', '')
            keyword = request.GET.get('keyword', '')
            days = int(request.GET.get('days', 30))
              # 默认获取30天的数据   
            with open ("brand_config.json","w",encoding="utf-8") as f:
                json.dump({"brand_name":brand_name,"keyword":keyword},f,ensure_ascii=False)
            cache_key = f"dashboard_data_{brand_name}_{keyword}_{days}"
            # 尝试从缓存中获取数据
            cached_data = cache.get(cache_key)
            if cached_data:
                return JsonResponse({'data': cached_data,  'from_cache': True})
            # 计算日期范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            # 查询提及数据
            mention_query = Mention_percentage.objects.filter(
                created_at__range=[start_date, end_date],keyword_name__icontains=keyword
            )
            if not mention_query.exists():
                # 如果没有数据，返回特殊标记
                return JsonResponse({
                    'no_data': True, 
                    'brand_name': brand_name, 
                    'keyword_name': keyword,
                    'status': 'no_data'
                })
            data = {
                'r_brand_amount': list(mention_query.values_list('r_brand_amount', flat=True)),
                'nr_brand_amount': list(mention_query.values_list('nr_brand_amount', flat=True)),
                'link_amount': list(mention_query.values_list("link_amount", flat=True)),
                "keyword_name": list(mention_query.values_list('keyword_name', flat=True)),
                "brand_name": list(mention_query.values_list('brand_name', flat=True)),
                "created_at": list(mention_query.values_list('created_at', flat=True)),
                    }
            return JsonResponse({'data': data, 'status': 'success'})
        
        except Exception as e:
            return JsonResponse({'error': str(e), 'status': 'error'}, status=500)
    
    return JsonResponse({'error': 'Invalid request method', 'status': 'error'}, status=405)

# 托管Dash应用
def dashboard_view(request):
    # 确保Dash应用已注册
    try:
        # 尝试获取Dash应用
        dash_app = StatelessApp.objects.get(slug='DashboardApp')
    except StatelessApp.DoesNotExist:
        # 如果不存在，创建一个
        dash_app = StatelessApp.objects.create(
            slug='DashboardApp',
            app_name='DashboardApp'
        )
    
    return render(request, 'mvp/dashboard.html')

from .models import Notification
@login_required_new_tab
def redirect_to_create_order(request):
    """从Dash应用重定向到订单创建页面，并预填品牌和关键词"""
    brand_name = request.GET.get('brand_name', '')
    keyword_name = request.GET.get('keyword_name', '')
    
    # 将品牌和关键词保存到session中，以便在创建订单页面使用
    request.session['prefilled_brand'] = brand_name
    request.session['prefilled_keyword'] = keyword_name
    
    # 重定向到订单创建页面
    return redirect('mvp:create_order')

@login_required_new_tab
def notification_list(request):
    """显示用户的所有通知"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # 标记所有通知为已读
    notifications.update(is_read=True)
    
    return render(request, 'mvp/notification_list.html', {'notifications': notifications})

@login_required_new_tab
def unread_notification_count(request):
    """获取未读通知数量"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required_new_tab
def mark_notification_read(request, notification_id):
    """
    标记通知为已读
    """
    try:
        notification = Notification.objects.get(id=notification_id, user=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': '通知不存在'})