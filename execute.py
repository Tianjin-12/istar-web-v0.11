import os
import subprocess
import sys

def run_crawler():
    """运行爬虫脚本"""
    print("开始运行爬虫脚本...")
    try:
        subprocess.run([sys.executable, "crabbing.py"], check=True)
        print("爬虫脚本运行")
        return True
    except subprocess.CalledProcessError as e:
        print(f"爬虫脚本运行出错: {e}")
        return False
def run_questioning():
    print("开始运行聚类问题脚本...")
    try:
        subprocess.run([sys.executable, "question_bank_construction251128.py"], check=True)
        print("聚类问题脚本运行")
        return True
    except subprocess.CalledProcessError as e:
        print(f"聚类问题脚本运行出错: {e}")
        return False    
def run_statistics():
    """运行统计脚本"""
    print("开始运行统计脚本...")
    try:
        subprocess.run([sys.executable, "\\Users\\meiho\\OneDrive\\Desktop\\MVP2\\myproject\\summary.py"], check=True)
        print("统计脚本运行")
        return True
    except subprocess.CalledProcessError as e:
        print(f"统计脚本运行出错: {e}")
        return False    
def main():
    print("=== 问题库系统 ===")
    if not os.path.exists('.env'):
        print("错误: .env 不存在")
        return
    if not run_questioning():
        print("聚类运行失败，终止流程")
        return
    if not os.path.exists('question_bank.csv'):
        print("错误: 问题文件 question_bank.csv 不存在")
        return
        
    print("=== 品牌提及统计系统 ===")
    
    # 检查配置文件是否存在
    if not os.path.exists('brand_config.json'):
        print("错误: 品牌配置文件 brand_config.json 不存在")
        return
    if not run_crawler():
        print("爬虫运行失败，终止流程")
        return
    
    # 检查结果文件是否存在
    if not os.path.exists('result.txt'):
        print("错误: 结果文件 result.txt 不存在，爬虫可能未成功获取数据")
        return
    
    if not run_statistics():
        print("统计运行失败")
        return
    print("=== 流程完成，开始分析 ===")

if __name__ == "__main__":
    main()