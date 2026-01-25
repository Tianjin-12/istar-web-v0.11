from playwright.sync_api import sync_playwright
import json
import os
import sys
import csv, itertools
import time
from datetime import datetime, timedelta
import re

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')

import django
django.setup()

from mvp.models import QuestionBank, AIAnswer, AILink

# ========================================
# 数据库适配函数
# ========================================

def check_ai_answer_cache(keyword):
    """检查AI回答缓存(1天)"""
    threshold = datetime.now() - timedelta(days=1)
    cached_count = AIAnswer.objects.filter(
        keyword=keyword,
        answer_date=datetime.now().date(),
        created_at__gte=threshold
    ).count()
    return cached_count > 0, cached_count

def load_questions_for_crabbing(keyword):
    """从数据库加载问题库用于爬取"""
    questions = list(QuestionBank.objects.filter(
        keyword=keyword
    ).order_by('cluster_id').values('cluster_id', 'generated_question'))
    
    # 格式化为 droped_questions.csv 的格式: [index, cluster_id, intent, question]
    formatted_questions = []
    for i, q in enumerate(questions, 1):
        formatted_questions.append({
            'index': str(i),
            'cluster_id': q['cluster_id'],
            'intent': '',  # 可以从数据库获取
            'question': q['generated_question']
        })
    
    return formatted_questions

def save_answer_to_db(keyword, question_id, question_text, answer_text):
    """保存AI回答到数据库"""
    today = datetime.now().date()
    answer, created = AIAnswer.objects.get_or_create(
        keyword=keyword,
        question_id=question_id,
        question_text=question_text,
        answer_date=today,
        defaults={'answer_text': answer_text}
    )
    return answer

def save_links_to_db(answer, links):
    """保存链接到数据库"""
    link_objs = [
        AILink(answer=answer, link_url=link)
        for link in links
    ]
    AILink.objects.bulk_create(link_objs, batch_size=50)

# ========================================
# 原有函数
# ========================================

def crabbing(browser, index, question):
    send_ds="//div[@class='_7436101 ds-icon-button ds-icon-button--l ds-icon-button--sizing-container']/div[@class='ds-icon-button__hover-bg']"
    def wait():
        last_text = ""
        same_count = 0
        while same_count < 10:  # 连续10秒内容不变即为完成
            # 获取最新消息文本
            messages = page1.query_selector_all('[class*="message"]')
            if messages:
                current_text = messages[-1].inner_text()
                if current_text == last_text:
                    same_count += 1  # 内容相同，计数+1
                else:
                    same_count = 0  # 内容变化，重置计数
                    last_text = current_text
                    print(f"生成中... ")

            time.sleep(1)  # 每秒检查一次
        return 0

    def collect_url():
        try:
            # 尝试多种方式定位元素
            selectors = [
                "//div[@class='f93f59e4']",
                "._source-links-button",  # CSS 选择器
                "[class*='source-links']"  # 包含 source-links 的类
            ]
            
            element_found = False
            for selector in selectors:
                try:
                    if selector.startswith("//"):  # XPath
                        element_count = page1.locator(selector).count()
                        if element_count > 0:
                            page1.click(selector)
                            element_found = True
                            print(f"通过XPath {selector} 找到并点击了元素")
                            break
                    else:  # CSS 选择器
                        element_count = page1.locator(selector).count()
                        if element_count > 0:
                            page1.click(selector)
                            element_found = True
                            print(f"通过CSS选择器 {selector} 找到并点击了元素")
                            break
                except:
                    continue
            
            if not element_found:
                print("未找到相关元素，尝试直接查找链接")
                # 直接查找所有链接
                link_selectors = [
                    "//div[@class='dc433409']/a",
                    "a[href*='http']",  # 包含http的链接
                    "[class*='source-link'] a"
                ]
                
                links_found = []
                for link_selector in link_selectors:
                    try:
                        if link_selector.startswith("//"):
                            links = page1.query_selector_all(link_selector)
                        else:
                            links = page1.query_selector_all(link_selector)
                        
                        if links:
                            links_found = links
                            print(f"通过选择器 {link_selector} 找到了 {len(links)} 个链接")
                            break
                    except:
                        continue
                
                if not links_found:
                    print("未找到任何链接")
                    return 0
            else:
                # 等待页面加载
                page1.wait_for_timeout(2000)
                # 查找链接s元素
                links_found = page1.query_selector_all("//div[@class='dc433409']/a")
                print(f"找到 {len(links_found)} 个链接元素")
            
            # 提取每个元素的 href 属性
            links = []
            for i, element in enumerate(links_found):
                try:
                    href = element.get_attribute("href")
                    print(f"链接 {i}: {href}")
                    if href and href.startswith(('http://', 'https://')):  # 确保是有效的链接
                        links.append(href)
                        print(f"添加链接: {href}")
                    else:
                        print(f"链接 {i} 的 href 属性无效或为空")
                except Exception as e:
                    print(f"处理链接 {i} 时出错: {e}")
                     
            print(f"成功收集 {len(links)} 个链接")
            return links
        except Exception as e:
            print(f"收集链接时出错: {e}")
            return []
    """在同一个浏览器实例中处理问题"""
    page_list_aa = browser.pages
    print(f'当前有 {len(page_list_aa)} 个页面')

    # 使用第一个页面
    page1 = page_list_aa[0]

    # 确保页面已经加载
    if page1.url != 'https://chat.deepseek.com/':
        page1.goto('https://chat.deepseek.com')
        page1.wait_for_timeout(5000)

    # 清除之前的对话内容
    try:
        # 尝试点击清除对话按钮
        clear_button = page1.locator("//button[contains(@class, 'clear')]")
        if clear_button.count() > 0 and clear_button.is_visible():
            clear_button.click()
            page1.wait_for_timeout(5000)
    except:
        # 如果清除按钮不可用，尝试刷新页面
        page1.reload()
        page1.wait_for_timeout(5000)

    # 等待页面加载完成
    page1.wait_for_timeout(5000)


    # 填写问题
    textarea = page1.locator("//textarea")
    textarea.fill("")
    textarea.fill(question)

    # 处理深度思考按钮
    button_selector = "//div[@class='ec4f5d61']/button[1]"
    button = page1.locator(button_selector)
    class_name = button.get_attribute("class")

    if "selected ds-toggle-button" in class_name:
        button.click()
        print("深度思考按钮已关闭")
    else:
        print("深度思考按钮已处于关闭状态，无需点击")

    # 处理联网搜索按钮
    button_selector2 = "//div[@class='ec4f5d61']/button[2]"
    button2 = page1.locator(button_selector2)
    class_name2 = button2.get_attribute("class")

    if "selected ds-toggle-button" in class_name2:
        print("联网搜索按钮已处于按下状态，无需点击")
    else:
        button2.click()
        print("联网搜索按钮已点击")

    # 发送问题
    page1.click(send_ds)

    # 等待回答生成
    wait()

    # 获取结果
    result_list = page1.locator("//div[@class='ds-message _63c77b1']/div[@class='ds-markdown']").all()
    
    # 提取所有回答文本
    answer_text = ""
    for res in result_list:
        text = res.inner_text()
        print(text)
        answer_text += text + "\n\n"
    
    # 收集链接
    links = collect_url()
    
    return answer_text, links

    # 如果需要更多回答，可以点击继续生成
    num = 1  # 爬取次数为num+1次
    all_links = links  # 保存所有链接
    
    for i in range(num):
        try:
            continue_button = page1.locator("//div[@class='ds-icon-button db183363'][2]")
            if continue_button.count() > 0 and continue_button.is_visible():
                continue_button.click()
            else:
                page1.click("//div[@class='_5a8ac7a a084f19e']")
            page1.fill("//textarea", question)
            page1.click(send_ds)
            wait()
            result_list = page1.locator("//div[@class='ds-message _63c77b1']/div[@class='ds-markdown']").all()
            for res in result_list:
                text = res.inner_text()
                print(text)
                answer_text += text + "\n\n"
            # 收集更多链接
            more_links = collect_url()
            all_links.extend(more_links)
        except Exception as e:
            print(f"继续生成回答时出错: {e}")
            break
    
    print(f"第{index}个问题已处理")
    page1.wait_for_timeout(3000)
    
    return answer_text, all_links


# 主程序
def main():
    # 创建浏览器实例（只创建一次）
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            user_data_dir=r"C:\Users\meiho\AppData\Local\Microsoft\Edge\User Data\MVP",
            headless=False,
            no_viewport=True,
            args=['--start-maximized']
        )

        # 初始化页面
        page_list_aa = browser.pages
        if len(page_list_aa) == 0:
            page1 = browser.new_page()
        else:
            page1 = page_list_aa[0]

        # 加载stealth脚本并访问网站
        js_data = open('stealth.min.js', 'r', encoding="utf-8").read()
        page1.add_init_script(js_data)
        page1.goto('https://chat.deepseek.com')
        page1.wait_for_timeout(3000)

        # 准备问题数据
        with open("question_bank.csv", "r", encoding="utf-8-sig") as r, \
                open("droped_questions.csv", "w", encoding="utf-8-sig") as w:
            next(r)
            w.writelines(r)

        # 处理所有问题
        with open("droped_questions.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                try:
                    if len(row) >= 4:  # 确保行有足够的列
                        crabbing(browser, row[0], row[3])
                        print(f"已完成问题 {row[0]} 的处理")
                    else:
                        print(f"跳过无效行: {row}")
                except Exception as e:
                    print(f"处理问题 {row[0]} 时出现错误: {e}")
                    continue

        print("所有问题处理完成！")
        page1.wait_for_timeout(3000)

 
if __name__ == "__main__":
    main()

# ========================================
# 数据库版本主函数
# ========================================

def collect_answers_with_db(keyword):
    """收集AI回答(数据库版本)"""
    try:
        # 缓存检查
        has_cache, count = check_ai_answer_cache(keyword)
        if has_cache:
            print(f"使用缓存: 找到 {count} 个回答")
            return True
        
        # 从数据库加载问题库
        questions = load_questions_for_crabbing(keyword)
        print(f"从数据库加载了 {len(questions)} 个问题")
        
        # 创建浏览器实例
        with sync_playwright() as p:
            browser = p.chromium.launch_persistent_context(
                executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                user_data_dir=r"C:\Users\meiho\AppData\Local\Microsoft\Edge\User Data\MVP",
                headless=False,
                no_viewport=True,
                args=['--start-maximized']
            )
            
            # 初始化页面
            page_list_aa = browser.pages
            if len(page_list_aa) == 0:
                page1 = browser.new_page()
            else:
                page1 = page_list_aa[0]
            
            # 加载stealth脚本并访问网站
            stealth_js_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'stealth.min.js')
            if os.path.exists(stealth_js_path):
                js_data = open(stealth_js_path, 'r', encoding="utf-8").read()
                page1.add_init_script(js_data)
            else:
                print("警告: 找不到 stealth.min.js 文件")
            
            page1.goto('https://chat.deepseek.com')
            page1.wait_for_timeout(3000)
            
            # 处理所有问题
            total_count = len(questions)
            for i, q in enumerate(questions, 1):
                try:
                    print(f"\n=== 处理第 {i}/{total_count} 个问题 ===")
                    
                    # 调用爬取函数
                    answer_text, links = crabbing(browser, q['index'], q['question'])
                    
                    # 保存到数据库
                    answer = save_answer_to_db(
                        keyword=keyword,
                        question_id=q['index'],
                        question_text=q['question'],
                        answer_text=answer_text
                    )
                    
                    # 保存链接
                    if links:
                        save_links_to_db(answer, links)
                        print(f"保存了 {len(links)} 个链接")
                    
                    print(f"已完成问题 {q['index']}, 进度: {i}/{total_count}")
                    
                except Exception as e:
                    print(f"处理问题 {q['index']} 时出错: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"\n所有问题处理完成！共 {total_count} 个问题")
            page1.wait_for_timeout(3000)
        
        return True
        
    except Exception as e:
        print(f"收集AI回答时出错: {str(e)}")
        import traceback
        traceback.print_exc()
        raise e

