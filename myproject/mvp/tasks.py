# myproject/mvp/tasks.py
from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone
from .models import Order
import time
from django.contrib.auth.models import User  # 添加User模型导入
from .models import Order, Notification 

@shared_task
def process_daily_orders():
    """
    每日定时任务：处理当天所有待处理的订单
    """
    today = timezone.now().date()
    pending_orders = Order.objects.filter(
        created_at__date=today,
        status='pending'
    )
    
    for order in pending_orders:
        # 为每个待处理订单启动异步任务
        process_order.delay(order.id)
    
    return f"已启动处理 {pending_orders.count()} 个待处理订单"

@shared_task
def process_order(order_id):
    """
    处理订单的异步任务
    """
    try:
        # 获取订单对象
        order = Order.objects.get(id=order_id)
        
        # 更新订单状态为处理中
        order.status = 'processing'
        order.save()
        
        # 发送处理中通知
        send_notification.delay(
            order.user.id, 
            f"您的订单 {order.id} 开始处理",
            order.id
        )
        
        # 模拟订单处理过程
        time.sleep(5)  # 模拟耗时操作
        
        # 这里可以添加实际的订单处理逻辑
        # 例如：数据分析、报告生成等
        
        # 更新订单状态为已完成
        order.status = 'completed'
        order.save()
        
        # 发送完成通知
        send_notification.delay(
            order.user.id, 
            f"您的订单 {order.id} 已完成处理",
            order.id
        )
        
        return f"订单 {order_id} 处理完成"
        
    except Order.DoesNotExist:
        return f"订单 {order_id} 不存在"
    except Exception as e:
        # 如果处理失败，更新订单状态为失败
        try:
            order = Order.objects.get(id=order_id)
            order.status = 'failed'
            order.save()
            
            # 发送失败通知
            send_notification.delay(
                order.user.id, 
                f"您的订单 {order.id} 处理失败: {str(e)}",
                order.id
            )
        except:
            pass
        return f"处理订单 {order_id} 时出错: {str(e)}"

@shared_task
def send_notification(user_id, message, order_id=None):
    """
    发送通知的异步任务
    """
    try:
        from .models import Notification
        user = User.objects.get(id=user_id)
        
        # 如果提供了订单ID，获取订单对象
        order = None
        if order_id:
            order = Order.objects.get(id=order_id)
        
        # 创建数据库通知
        notification = Notification.objects.create(
            user=user,
            order=order,
            message=message
        )
        
        return f"已向用户 {user_id} 发送通知: {message}"
        
    except User.DoesNotExist:
        return f"用户 {user_id} 不存在"
    except Order.DoesNotExist:
        return f"订单 {order_id} 不存在"
    except Exception as e:
        return f"发送通知时出错: {str(e)}"