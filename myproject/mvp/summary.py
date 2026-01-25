import os
import json
import re
import sys
import datetime
from openai import OpenAI 
from dotenv import load_dotenv
import csv
import ast

# 添加Django项目路径
sys.path.append(os.path.join(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

import django
django.setup()

from mvp.models import Mention_percentage, AIAnswer, AILink, QuestionScore, QuestionBank

# 加载环境变量
load_dotenv()
key = os.getenv("API_KEY")
prompt4 = os.getenv("prompt4")

# ========================================
# 数据库适配函数
# ========================================

def load_answers_from_db(keyword):
    """从数据库加载AI回答"""
    today = datetime.datetime.now().date()
    answers = list(AIAnswer.objects.filter(
        keyword=keyword,
        answer_date=today
    ).order_by('question_id').values('question_id', 'question_text', 'answer_text'))
    
    # 构建索引-回答映射
    s_dict = {}
    for ans in answers:
        s_dict[ans['question_id']] = ans['answer_text']
    
    return s_dict, len(answers)

def load_question_bank_for_summary(keyword):
    """从数据库加载问题库用于评分"""
    questions = list(QuestionBank.objects.filter(
        keyword=keyword
    ).order_by('cluster_id').values('cluster_id', 'generated_question'))
    
    # 构建问题ID到问题文本的映射
    org_questions = {}
    for i, q in enumerate(questions, 1):
        org_questions[str(i)] = q['generated_question']
    
    return org_questions

def load_scores_from_db(keyword):
    """从数据库加载评分"""
    today = datetime.datetime.now().date()
    scores = list(QuestionScore.objects.filter(
        keyword=keyword,
        answer_date=today
    ).values_list('question_id', 'score'))
    
    return {str(qid): score for qid, score in scores}

def load_links_for_summary(keyword):
    """从数据库加载链接"""
    today = datetime.datetime.now().date()
    answer_ids = list(AIAnswer.objects.filter(
        keyword=keyword,
        answer_date=today
    ).values_list('id', flat=True))
    
    # 构建问题ID到链接列表的映射
    link_mentions = {}
    for answer_id in answer_ids:
        # 获取关联的问题ID
        try:
            answer = AIAnswer.objects.get(id=answer_id)
            links = list(AILink.objects.filter(answer_id=answer_id).values_list('link_url', flat=True))
            link_mentions[str(answer.question_id)] = links
        except AIAnswer.DoesNotExist:
            continue
    
    return link_mentions

# ========================================
# 原有主函数(兼容模式)
# ========================================

# 读取品牌配置(兼容模式,但从参数获取)
# brand_path = 'result.txt'
# link_path='link.txt'

# 读取品牌配置
# try:
#     with open('myproject\\brand_config.json', 'r', encoding='utf-8') as f:
#         brand_config = json.load(f)
#     brand_name = brand_config['brand_name']
#     website = brand_config['link']
#     keyword = brand_config['keyword']
# except FileNotFoundError:
#     print("警告: brand_config.json 不存在,使用默认值")
#     brand_name = ""
#     website = ""
#     keyword = "新能源汽车"

# 读取result.txt内容(兼容模式)
# try:
#     with open(brand_path, 'r', encoding='utf-8') as f:
#         result_content = f.read()
#     # 读取link.txt内容
#     try:
#         with open(link_path, 'r', encoding='utf-8') as f:
#             link_content = f.read()
#     except FileNotFoundError:
#         link_content = ""
#     
#     # 使用正则表达式按"=== 问题 X ==="格式分割每个回答
#     questions = re.split(r'=== 问题 \d+.*? ===', result_content)
#     index = re.findall(r"=== 问题 (\d+) ===", result_content)
#     
#     # 过滤掉空字符串
#     questions = [q.strip() for q in questions if q.strip()]
#     
#     total_questions = len(questions)
#     print(f"读取了 {total_questions} 个回答")
#     
#     org_questions = {}
#     with open("droped_questions.csv","r",encoding="utf-8-sig") as f:
#         reader = csv.reader(f)
#         for row in reader:
#             if len(row) >= 4:
#                 org_questions[row[0]] = row[3]
#     
#     # 调用LLM进行评分
#     if key:
#         client = OpenAI(api_key=key, base_url="https://api.moonshot.cn/v1")
#         completion = client.chat.completions.create(
#             model="kimi-k2-0905-preview",
#             messages=[{"role": "user", "content": prompt4 + "\n".join(str(org_questions))}],
#             temperature=0,
#         )
#         result = completion.choices[0].message.content
#         print(result)
#         
#         # 解析评分结果
#         try:
#             cleaned_result = result.replace("```json", "").strip()
#             scores_data = ast.literal_eval(cleaned_result)
#             if isinstance(scores_data, dict):
#                 scores_dict = scores_data
#             else:
#                 scores_dict = {}
#         except Exception as e:
#             print(f"解析评分结果时出错: {e}")
#             scores_dict = {}
#     else:
#         print("警告: 未能读取到API密钥")
#         scores_dict = {}
#     
#     # 构建回答映射
#     s_dict = dict(zip(index, questions))
#     
#     # 找出得分3和4的问题ID
#     high_recommend_ids = [qid for qid, score in scores_dict.items() if score in [3, 4]]
#     
#     # 统计品牌提及
#     brand_mentioned_count = 0
#     r_brand_mentioned_count = 0
#     nr_brand_mentioned_count = 0
#     
#     for i, q in s_dict.items():
#         if brand_name in q:
#             brand_mentioned_count += 1
#             if i in high_recommend_ids:
#                 r_brand_mentioned_count += 1
#             else:
#                 nr_brand_mentioned_count += 1
#     
#     # 计算品牌提及百分比
#     brand_amount = (brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
#     r_brand_amount = (r_brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
#     nr_brand_amount = (nr_brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
#     
#     # 统计链接提及
#     link_mentioned_count = 0
#     r_link_mentioned_count = 0
#     nr_link_mentioned_count = 0
#     
#     for i, q in s_dict.items():
#         if website in q:
#             link_mentioned_count += 1
#             if i in high_recommend_ids:
#                 r_link_mentioned_count += 1
#             else:
#                 nr_link_mentioned_count += 1
#     
#     # 计算链接提及百分比
#     link_amount = (link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
#     r_link_amount = (r_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
#     nr_link_amount = (nr_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
#     
#     # 保存到数据库
#     field_name = keyword
#     result = Mention_percentage.objects.create(
#         brand_name=brand_name,
#         brand_amount=brand_amount,
#         r_brand_amount=r_brand_amount,
#         nr_brand_amount=nr_brand_amount,
#         link_amount=link_amount,
#         r_link_amount=r_link_amount,
#         nr_link_amount=nr_link_amount,
#         keyword_name=keyword,
#         field_name=field_name,
#         created_at=datetime.datetime.now()
#     )
#     
#     print(f"数据处理完成,总品牌提及率: {brand_amount:.2f}%, 推荐类品牌提及率: {r_brand_amount:.2f}%, 非推荐类品牌提及率: {nr_brand_amount:.2f}%")
#     print(f"总链接提及率: {link_amount:.2f}%, 推荐类链接提及率: {r_link_amount:.2f}%, 非推荐类链接提及率: {nr_link_amount:.2f}%")
# except FileNotFoundError as e:
#     print(f"错误: 找不到文件 - {e}")
# except Exception as e:
#     print(f"处理过程中出错: {e}")
#     import traceback
#     traceback.print_exc()

# ========================================
# 数据库版本主函数
# ========================================

def analyze_with_db(keyword, brand):
    """分析订单(数据库版本)"""
    try:
        # 从数据库加载数据
        s_dict, total_questions = load_answers_from_db(keyword)
        print(f"从数据库加载了 {total_questions} 个AI回答")
        
        org_questions = load_question_bank_for_summary(keyword)
        print(f"从数据库加载了 {len(org_questions)} 个原始问题")
        
        scores_dict = load_scores_from_db(keyword)
        print(f"从数据库加载了 {len(scores_dict)} 个评分")
        
        # 如果数据库中没有评分,则跳过评分逻辑,所有问题默认得分为0
        if not scores_dict:
            print("警告: 数据库中没有评分数据,所有问题将得分为0")
            scores_dict = {str(i): 0 for i in range(1, len(org_questions)+1)}
        
        # 找出得分3和4的问题ID
        high_recommend_ids = [qid for qid, score in scores_dict.items() if score in [3, 4]]
        print(f"得分3和4的问题ID: {high_recommend_ids}")
        
        # 计算品牌提及百分比
        brand_mentioned_count = 0
        r_brand_mentioned_count = 0
        nr_brand_mentioned_count = 0
        
        for i, answer_text in s_dict.items():
            if brand in answer_text:
                brand_mentioned_count += 1
                if i in high_recommend_ids:
                    r_brand_mentioned_count += 1
                else:
                    nr_brand_mentioned_count += 1
        
        brand_amount = (brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
        r_brand_amount = (r_brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
        nr_brand_amount = (nr_brand_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
        
        # 从数据库加载链接
        link_mentions = load_links_for_summary(keyword)
        print(f"从数据库加载了 {len(link_mentions)} 个问题的链接")
        
        # 统计链接提及
        website = brand  # 这里需要从 Order 获取,简化处理
        link_mentioned_count = 0
        r_link_mentioned_count = 0
        nr_link_mentioned_count = 0
        
        for qid in s_dict.keys():
            links = link_mentions.get(qid, [])
            if any(website in link for link in links):
                link_mentioned_count += 1
                if qid in high_recommend_ids:
                    r_link_mentioned_count += 1
                else:
                    nr_link_mentioned_count += 1
        
        link_amount = (link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
        r_link_amount = (r_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
        nr_link_amount = (nr_link_mentioned_count / total_questions) * 100 if total_questions > 0 else 0
        
        # 保存到数据库
        field_name = keyword  # 简化处理,实际需要从配置获取
        result = Mention_percentage.objects.create(
            brand_name=brand,
            keyword_name=keyword,
            field_name=field_name,
            brand_amount=brand_amount,
            r_brand_amount=r_brand_amount,
            nr_brand_amount=nr_brand_amount,
            link_amount=link_amount,
            r_link_amount=r_link_amount,
            nr_link_amount=nr_link_amount,
            created_at=datetime.datetime.now()
        )
        
        print(f"数据处理完成,总品牌提及率: {brand_amount:.2f}%, 推荐类品牌提及率: {r_brand_amount:.2f}%, 非推荐类品牌提及率: {nr_brand_amount:.2f}%")
        print(f"总链接提及率: {link_amount:.2f}%, 推荐类链接提及率: {r_link_amount:.2f}%, 非推荐类链接提及率: {nr_link_amount:.2f}%")
        
        return result.id
        
    except Exception as e:
        print(f"分析订单时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e
