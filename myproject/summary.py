import os
import json
import re
import sys
import datetime
from openai import OpenAI 
from dotenv import load_dotenv
import time
import csv
import ast
# 添加Django项目路径
sys.path.append(os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

import django
django.setup()

from mvp.models import Mention_percentage

brand_path = 'result.txt'
link_path='link.txt'

# 读取品牌配置
with open('brand_config.json', 'r', encoding='utf-8') as f:
    brand_config = json.load(f)

# 获取单个品牌名称和网站
brand_name = brand_config['brands'][0]['brand_name']
website = brand_config['brands'][0]['website']
keyword = brand_config['brands'][0]['keyword']

# 读取result.txt内容
with open(brand_path, 'r', encoding='utf-8') as f:
    result_content = f.read()

# 读取link.txt内容（如果存在）
try:
    with open(link_path, 'r', encoding='utf-8') as f:
        link_content = f.read()
except FileNotFoundError:
    link_content = ""

# 使用正则表达式按"=== 问题 X ==="格式分割每个回答
questions = re.split(r'=== 问题 \d+.*? ===', result_content)
index = re.findall(r"=== 问题 (\d+) ===", result_content)

# 过滤掉空字符串
questions = [q.strip() for q in questions if q.strip()]

# 计算总回答数
load_dotenv()
key = os.getenv("API_KEY")
prompt4 = os.getenv("prompt4")
total_questions = len(questions)
if key:
    print("成功读取到API密钥！")    
else:
    print("错误：未能读取到API密钥，请检查 .env 文件。")
org_questions = {}
with open("droped_questions.csv","r",encoding="utf-8-sig") as f:
    reader = csv.reader(f)
    for row in reader:
        if len(row) >= 4:  # 确保行有足够的列
            org_questions[row[0]] = row[3]
        else:
            print(f"跳过无效行: {row}")
print(org_questions)

client = OpenAI(api_key = key,base_url="https://api.moonshot.cn/v1",)
completion = client.chat.completions.create(
    model="kimi-k2-0905-preview",
    messages=[{"role": "user", "content": prompt4 + "\n".join(str(org_questions))}],
    temperature=0,
    )
result = completion.choices[0].message.content
print(result)
# 解析Kimi返回的评分结果
try:
    # 清理结果字符串，移除可能的markdown代码块标记
    cleaned_result = result.replace("```json", "").strip()
    scores_data = ast.literal_eval(cleaned_result)
    if isinstance(scores_data, dict):
        scores_dict = scores_data
    else:
        scores_dict = {}
except Exception as e:
    print(f"解析评分结果时出错: {e}")
    scores_dict = {}

# 找出得分3和4的问题ID
high_recommend_ids = [qid for qid, score in scores_dict.items() if score in [3, 4]]
print(f"得分3和4的问题ID: {high_recommend_ids}")
s_dict = dict(zip(index,questions))
# 统计品牌提及
brand_mentioned_count = 0
r_brand_mentioned_count = 0  # 推荐类品牌提及数
nr_brand_mentioned_count = 0  # 非推荐类品牌提及数

for i, q in s_dict.items():
    if brand_name in q:
        brand_mentioned_count += 1
        # 检查该问题是否属于推荐类（得分3或4）
        if i in high_recommend_ids:
            r_brand_mentioned_count += 1
        else:
            nr_brand_mentioned_count += 1

# 计算品牌提及百分比
brand_amount = (brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
r_brand_amount = (r_brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
nr_brand_amount = (nr_brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0

# 统计链接提及
link_mentioned_count = 0
r_link_mentioned_count = 0  # 推荐类链接提及数
nr_link_mentioned_count = 0  # 非推荐类链接提及数


for i, q in s_dict.items():
    if website in q:
        link_mentioned_count += 1
        # 检查该问题是否属于推荐类（得分3或4）
        if i in high_recommend_ids:
            r_link_mentioned_count += 1
        else:
            nr_link_mentioned_count += 1

# 计算链接提及百分比
link_amount = (link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
r_link_amount = (r_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
r_link_amount = (r_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
nr_link_amount = (nr_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0

# 保存品牌提及数据到数据库
Mention_percentage.objects.create(
    brand_name=brand_name,
    brand_amount=brand_amount,
    r_brand_amount=r_brand_amount,
    nr_brand_amount=nr_brand_amount,
    link_amount=link_amount,
    r_link_amount=r_link_amount,
    nr_link_amount=nr_link_amount,
    keyword_name=keyword,
    created_at=datetime.datetime.now()
)
print(f"数据处理完成，总品牌提及率: {brand_amount:.2f}%, 推荐类品牌提及率: {r_brand_amount:.2f}%, 非推荐类品牌提及率: {nr_brand_amount:.2f}%")
print(f"总链接提及率: {link_amount:.2f}%, 推荐类链接提及率: {r_link_amount:.2f}%, 非推荐类链接提及率: {nr_link_amount:.2f}%")