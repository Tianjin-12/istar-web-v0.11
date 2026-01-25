from celery import shared_task, chord, chain
from celery.result import AsyncResult
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Q
from .models import (
    Order, Notification, TaskLog,
    ZhihuQuestion, QuestionBank, AIAnswer, QuestionScore
)
from .redis_client import get_redis_client
import json
from datetime import datetime, timedelta


# ========================================
# 阶段1: 订单分组(每天00:00触发)
# ========================================

@shared_task(name='mvp.schedule_order_processing')
def schedule_order_processing():
    """凌晨0点触发: 按关键词分组订单并启动任务链"""
    pending_orders = Order.objects.filter(status='pending')
    
    # 按关键词分组
    keyword_groups = {}
    for order in pending_orders:
        keyword = order.keyword
        if keyword not in keyword_groups:
            keyword_groups[keyword] = []
        keyword_groups[keyword].append(order)
    
    # 对每个关键词启动任务链
    total_tasks = 0
    for keyword, orders in keyword_groups.items():
        # 启动关键词级任务链
        chain(
            check_cache_status.s(keyword),
            search_questions.s(keyword),
            build_question_bank.s(keyword),
            collect_ai_answers.s(keyword),
            score_questions.s(keyword),
            analyze_orders_by_keyword.s(keyword, [o.id for o in orders])
        ).apply_async()
        
        # 更新订单状态
        Order.objects.filter(id__in=[o.id for o in orders]).update(
            status='processing',
            current_stage='searching'
        )
        
        total_tasks += 1
    
    return f"已启动 {total_tasks} 个关键词的任务链"

# ========================================
# 阶段2: 缓存检查
# ========================================

@shared_task(name='mvp.check_cache_status')
def check_cache_status(keyword):
    """检查各阶段缓存状态"""
    # 检查知乎问题缓存(7天)
    threshold_7d = datetime.now() - timedelta(days=7)
    has_zhihu = ZhihuQuestion.objects.filter(
        keyword=keyword,
        created_at__gte=threshold_7d
    ).exists()
    
    # 检查问题库缓存(7天)
    has_question_bank = QuestionBank.objects.filter(
        keyword=keyword,
        created_at__gte=threshold_7d
    ).exists()
    
    # 检查AI回答缓存(1天)
    threshold_1d = datetime.now() - timedelta(days=1)
    today = datetime.now().date()
    has_answers = AIAnswer.objects.filter(
        keyword=keyword,
        answer_date=today,
        created_at__gte=threshold_1d
    ).exists()
    
    # 检查评分缓存(1天)
    has_scores = QuestionScore.objects.filter(
        keyword=keyword,
        answer_date=today,
        created_at__gte=threshold_1d
    ).exists()
    
    cache_status = {
        'zhihu': has_zhihu,
        'question_bank': has_question_bank,
        'answers': has_answers,
        'scores': has_scores
    }
    
    print(f"缓存状态[{keyword}]: {cache_status}")
    
    return cache_status

# ========================================
# 阶段3: 搜索知乎问题(7天缓存)
# ========================================

@shared_task(name='mvp.search_questions')
def search_questions(keyword):
    """搜索知乎问题并保存到数据库"""
    try:
        from .searching import searching_with_db
        
        # 创建任务日志
        task_log = TaskLog.objects.create(
            task_type='search_questions',
            status='running',
            started_at=timezone.now()
        )
        
        # 执行搜索(自动检查缓存)
        questions = searching_with_db(keyword, use_cache=True)
        
        # 更新任务日志
        task_log.status = 'completed'
        task_log.completed_at = timezone.now()
        task_log.duration = int((task_log.completed_at - task_log.started_at).total_seconds())
        task_log.save()
        
        return {'status': 'success', 'count': len(questions)}
        
    except Exception as e:
        # 记录错误
        task_log.status = 'failed'
        task_log.error_message = str(e)
        task_log.completed_at = timezone.now()
        task_log.save()
        raise e

# ========================================
# 阶段4: 构建问题库(7天缓存)
# ========================================

@shared_task(name='mvp.build_question_bank')
def build_question_bank(keyword):
    """构建问题库并保存到数据库"""
    try:
        from .question_bank import build_bank_with_db
        
        # 创建任务日志
        task_log = TaskLog.objects.create(
            task_type='build_question_bank',
            status='running',
            started_at=timezone.now()
        )
        
        # 构建问题库(自动检查缓存)
        questions = build_bank_with_db(keyword)
        
        # 更新任务日志
        task_log.status = 'completed'
        task_log.completed_at = timezone.now()
        task_log.duration = int((task_log.completed_at - task_log.started_at).total_seconds())
        task_log.save()
        
        return {'status': 'success', 'count': len(questions)}
        
    except Exception as e:
        task_log.status = 'failed'
        task_log.error_message = str(e)
        task_log.completed_at = timezone.now()
        task_log.save()
        raise e

# ========================================
# 阶段5: 收集AI回答(1天缓存)
# ========================================

@shared_task(name='mvp.collect_ai_answers')
def collect_ai_answers(keyword):
    """收集AI回答并保存到数据库"""
    try:
        from .crabbing import collect_answers_with_db
        
        # 创建任务日志
        task_log = TaskLog.objects.create(
            task_type='collect_ai_answers',
            status='running',
            started_at=timezone.now()
        )
        
        # 收集回答(自动检查缓存)
        result = collect_answers_with_db(keyword)
        
        # 更新任务日志
        task_log.status = 'completed'
        task_log.completed_at = timezone.now()
        task_log.duration = int((task_log.completed_at - task_log.started_at).total_seconds())
        task_log.save()
        
        return {'status': 'success'}
        
    except Exception as e:
        task_log.status = 'failed'
        task_log.error_message = str(e)
        task_log.completed_at = timezone.now()
        task_log.save()
        raise e

# ========================================
# 阶段6: 问题评分(1天缓存)
# ========================================

@shared_task(name='mvp.score_questions')
def score_questions(keyword):
    """对问题进行评分并保存到数据库"""
    try:
        from .question_bank import score_questions_with_db
        
        # 创建任务日志
        task_log = TaskLog.objects.create(
            task_type='score_questions',
            status='running',
            started_at=timezone.now()
        )
        
        # 评分(自动检查缓存)
        result = score_questions_with_db(keyword)
        
        # 更新任务日志
        task_log.status = 'completed'
        task_log.completed_at = timezone.now()
        task_log.duration = int((task_log.completed_at - task_log.started_at).total_seconds())
        task_log.save()
        
        return {'status': 'success'}
        
    except Exception as e:
        task_log.status = 'failed'
        task_log.error_message = str(e)
        task_log.completed_at = timezone.now()
        task_log.save()
        raise e

# ========================================
# 阶段7: 批量分析订单
# ========================================

@shared_task(name='mvp.analyze_orders_by_keyword')
def analyze_orders_by_keyword(keyword, order_ids):
    """批量分析关键词关联的所有订单"""
    from .summary import analyze_with_db
    
    results = []
    
    for order_id in order_ids:
        try:
            # 获取订单
            order = Order.objects.get(id=order_id)
            
            # 更新订单状态
            order.current_stage = 'analyzing'
            order.save()
            
            # 执行分析
            result_id = analyze_with_db(keyword, order.brand)
            
            # 更新订单状态
            order.status = 'completed'
            order.current_stage = 'completed'
            order.progress_percentage = 100
            order.is_cached = True  # 标记使用缓存
            order.save()
            
            # 发送通知
            send_notification.delay(
                user_id=order.user.id,
                message=f"订单 {order.id} 分析完成",
                order_id=order.id
            )
            
            results.append({
                'order_id': order_id,
                'status': 'success',
                'result_id': result_id
            })
            
        except Exception as e:
            # 更新订单状态
            order.status = 'failed'
            order.last_error = str(e)
            order.save()
            
            results.append({
                'order_id': order_id,
                'status': 'failed',
                'error': str(e)
            })
    
    return results

# ========================================
# 定时任务: 数据清理
# ========================================

@shared_task(name='mvp.cleanup_old_data')
def cleanup_old_data():
    """清理过期数据"""
    # 删除7天前的知乎问题
    threshold_7d = datetime.now() - timedelta(days=7)
    deleted_zhihu = ZhihuQuestion.objects.filter(
        created_at__lt=threshold_7d
    ).delete()
    
    # 删除7天前的问题库
    deleted_qb = QuestionBank.objects.filter(
        created_at__lt=threshold_7d
    ).delete()
    
    # 删除1天前的AI回答和链接
    threshold_1d = datetime.now() - timedelta(days=1)
    deleted_answers = AIAnswer.objects.filter(
        created_at__lt=threshold_1d
    ).delete()
    # AILink 会级联删除
    
    # 删除1天前的评分
    deleted_scores = QuestionScore.objects.filter(
        created_at__lt=threshold_1d
    ).delete()
    
    return {
        'zhihu': deleted_zhihu[0] if deleted_zhihu else 0,
        'question_bank': deleted_qb[0] if deleted_qb else 0,
        'answers': deleted_answers[0] if deleted_answers else 0,
        'scores': deleted_scores[0] if deleted_scores else 0
    }

@shared_task(name='mvp.archive_old_data')
def archive_old_data():
    """归档任务日志(1个月)"""
    import csv
    
    threshold_1m = datetime.now() - timedelta(days=30)
    
    # 查询1个月前的任务日志
    old_logs = TaskLog.objects.filter(
        started_at__lt=threshold_1m
    )
    
    # 导出为CSV
    filename = f"C:\\Users\\meiho\\OneDrive\\Desktop\\MVP2\\archive\\tasks\\{datetime.now().strftime('%Y-%m')}.csv"
    import os
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'order_id', 'task_type', 'status', 'retry_count', 
                        'error_message', 'started_at', 'completed_at', 'duration'])
        
        for log in old_logs:
            writer.writerow([
                log.id, log.order_id, log.task_type, log.status,
                log.retry_count, log.error_message, log.started_at,
                log.completed_at, log.duration
            ])
    
    # 删除数据库记录
    count = old_logs.count()
    old_logs.delete()
    
    return {'archived': count, 'filename': filename}

# ========================================
# 兼容性: 保留原有函数(但为空实现)
# ========================================

# 兼容性函数: process_order(不再使用,由 schedule_order_processing 替代)
@shared_task(name='mvp.process_order')
def process_order(order_id):
    """兼容性函数: 不再使用,由 schedule_order_processing 替代"""
    return {'status': 'deprecated', 'message': '请使用 schedule_order_processing 替代'}

# ========================================
# 保留原有辅助任务
# ========================================

@shared_task
def collect_and_save_results(results):
    """chord回调: 收集结果并同步重复订单状态"""
    redis_client = get_redis_client()

    orders_to_update = []

    for result in results:
        order_id = result['order_id']
        status = result['status']

        redis_key = f"order_mapping:{order_id}"
        duplicate_ids = redis_client.get(redis_key)

        if duplicate_ids:
            duplicate_ids = json.loads(duplicate_ids)

            for dup_id in duplicate_ids:
                try:
                    order = Order.objects.get(id=dup_id)
                    if status == "success":
                        order.status = 'completed'
                    else:
                        order.status = 'failed'
                    orders_to_update.append(order)
                except Order.DoesNotExist:
                    pass

            redis_client.delete(redis_key)

    if orders_to_update:
        Order.objects.bulk_update(orders_to_update, ['status'])

    return f"已同步 {len(orders_to_update)} 个重复订单状态"


@shared_task
def cleanup_backend():
    """凌晨4点触发: 清理未完成任务和缓存"""
    processing_orders = Order.objects.filter(status='processing')
    count = processing_orders.update(status='failed')

    from celery import current_app
    inspect = current_app.control.inspect()
    active_tasks = inspect.active()

    if active_tasks:
        for worker_name, tasks in active_tasks.items():
            for task in tasks:
                AsyncResult(task['id']).revoke(terminate=False)

    redis_client = get_redis_client()
    mapping_keys = redis_client.keys("order_mapping:*")
    if mapping_keys:
        redis_client.delete(*mapping_keys)

    return f"已标记 {count} 个处理中的订单为失败，并清理任务队列"


@shared_task(name='mvp.send_notification')
def send_notification(user_id, message, order_id=None):
    """发送通知的异步任务"""
    try:
        user = User.objects.get(id=user_id)

        order = None
        if order_id:
            order = Order.objects.get(id=order_id)

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
