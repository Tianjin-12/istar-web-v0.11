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
    is_light_on = models.BooleanField(default=False, verbose_name="灯泡状态")
    click_count = models.IntegerField(default=0, verbose_name="点击次数")
    task_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="任务ID")
    
    class Meta:
        verbose_name = "订单"
        verbose_name_plural = "订单"
        ordering = ['-created_at']
    
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
    
    def __str__(self):
        return f"通知 {self.id} - {self.user.username} - {self.order.id}"