from django.contrib import admin
from mvp.models import Mention_percentage
@admin.register(Mention_percentage)
class Mention_percentageAdmin(admin.ModelAdmin):
    list_display = ('brand_name', 'keyword_name', 'brand_amount')  # 列表页显示字段
    search_fields = ('brand_name', 'keyword_name')  # 搜索字段
    list_filter = ('brand_name', 'keyword_name')  # 过滤器

