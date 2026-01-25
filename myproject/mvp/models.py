# mvp/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User  # 导入User模型

class Mention_percentage(models.Model):
    brand_amount = models.FloatField(verbose_name="总品牌提及百分比")  # 浮点数字段
    r_brand_amount = models.FloatField(verbose_name="推荐类品牌提及百分比")
    nr_brand_amount = models.FloatField(verbose_name="非推荐类品牌提及百分比")
    link_amount = models.FloatField(verbose_name="总链接提及百分比")
    r_link_amount = models.FloatField(verbose_name="推荐类链接提及百分比")
    nr_link_amount = models.FloatField(verbose_name="非推荐类链接提及百分比")
    brand_name = models.CharField(max_length=100, verbose_name="品牌名称")  # 字符串字段
    keyword_name = models.CharField(max_length=100, verbose_name="关键约束词名称")
    field_name = models.CharField(max_length=100, verbose_name="行业名称")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")  # 自动创建时间
   
    class Meta:
        verbose_name = "提及百分比"
        verbose_name_plural = "提及百分比"
        indexes = [
            models.Index(fields=['brand_name', 'keyword_name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['field_name']),
        ]

    def __str__(self):
        return f"{self.brand_name} - {self.keyword_name}-{self.brand_amount}"  # 对象的字符串表示

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('completed', '已完成'),
        ('failed', '失败'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    keyword = models.CharField(max_length=255, verbose_name="关键词")
    brand = models.CharField(max_length=255, verbose_name="品牌词")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="状态")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    task_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="任务ID")
    
    # 新增字段: 任务追踪
    current_stage = models.CharField(max_length=50, blank=True, null=True, verbose_name="当前阶段")
    progress_percentage = models.IntegerField(default=0, verbose_name="进度百分比")
    last_error = models.TextField(blank=True, null=True, verbose_name="最后错误")
    retry_count = models.IntegerField(default=0, verbose_name="重试次数")
    is_cached = models.BooleanField(default=False, verbose_name="是否使用缓存")
    
    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['keyword']),
            models.Index(fields=['brand']),
        ]
    
    def __str__(self):
        return f"订单 {self.id} - {self.keyword} - {self.brand}"

class Notification(models.Model):
    """通知模型"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="相关订单")
    message = models.TextField(verbose_name="通知内容")
    is_read = models.BooleanField(default=False, verbose_name="是否已读")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"通知 {self.id} - {self.user.username} - {self.order.id}"

# 新增模型: 知乎问题缓存表(7天)
class ZhihuQuestion(models.Model):
    keyword = models.CharField(max_length=255, db_index=True, verbose_name="关键词")
    question_id = models.IntegerField(db_index=True, verbose_name="问题序号")
    question_text = models.TextField(verbose_name="问题内容")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "知乎问题缓存"
        verbose_name_plural = "知乎问题缓存"
        unique_together = [('keyword', 'question_id')]
        indexes = [
            models.Index(fields=['keyword', 'created_at']),
        ]

# 新增模型: 问题库缓存表(7天)
class QuestionBank(models.Model):
    keyword = models.CharField(max_length=255, db_index=True, verbose_name="关键词")
    cluster_id = models.IntegerField(db_index=True, verbose_name="聚类ID")
    main_intent = models.TextField(verbose_name="聚类意图")
    generated_question = models.TextField(verbose_name="生成的问题")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "问题库缓存"
        verbose_name_plural = "问题库缓存"
        indexes = [
            models.Index(fields=['keyword', 'cluster_id']),
            models.Index(fields=['created_at']),
        ]

# 新增模型: AI回答缓存表(1天)
class AIAnswer(models.Model):
    keyword = models.CharField(max_length=255, db_index=True, verbose_name="关键词")
    question_id = models.CharField(max_length=100, db_index=True, verbose_name="问题ID")
    question_text = models.TextField(verbose_name="问题内容")
    answer_text = models.TextField(verbose_name="AI回答")
    answer_date = models.DateField(db_index=True, verbose_name="回答日期")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "AI回答缓存"
        verbose_name_plural = "AI回答缓存"
        indexes = [
            models.Index(fields=['keyword', 'question_id']),
            models.Index(fields=['answer_date']),
        ]

# 新增模型: AI回答链接表(1天)
class AILink(models.Model):
    answer = models.ForeignKey(AIAnswer, on_delete=models.CASCADE, related_name='links', verbose_name="关联回答")
    link_url = models.TextField(verbose_name="链接URL")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "AI回答链接"
        verbose_name_plural = "AI回答链接"
        indexes = [
            models.Index(fields=['answer']),
        ]

# 新增模型: 问题评分缓存表(1天)
class QuestionScore(models.Model):
    keyword = models.CharField(max_length=255, db_index=True, verbose_name="关键词")
    question_id = models.CharField(max_length=100, db_index=True, verbose_name="问题ID")
    score = models.IntegerField(db_index=True, verbose_name="评分(0-4)")
    answer_date = models.DateField(db_index=True, verbose_name="评分日期")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")
    
    class Meta:
        verbose_name = "问题评分缓存"
        verbose_name_plural = "问题评分缓存"
        unique_together = [('keyword', 'question_id', 'answer_date')]
        indexes = [
            models.Index(fields=['keyword', 'question_id']),
            models.Index(fields=['answer_date']),
        ]

# 新增模型: 任务执行日志表(1个月)
class TaskLog(models.Model):
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, db_index=True, verbose_name="订单")
    task_type = models.CharField(max_length=50, db_index=True, verbose_name="任务类型")
    status = models.CharField(max_length=20, db_index=True, verbose_name="状态")
    retry_count = models.IntegerField(default=0, verbose_name="重试次数")
    error_message = models.TextField(blank=True, null=True, verbose_name="错误信息")
    started_at = models.DateTimeField(db_index=True, verbose_name="开始时间")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="完成时间")
    duration = models.IntegerField(blank=True, null=True, verbose_name="执行时长(秒)")
    
    class Meta:
        verbose_name = "任务执行日志"
        verbose_name_plural = "任务执行日志"
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['order', 'status']),
            models.Index(fields=['task_type', 'status']),
            models.Index(fields=['started_at']),
        ]