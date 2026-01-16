import os#切换当前工作目录
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    print(f"当前工作目录已切换至: {os.getcwd()}")    
except NameError:    
    print("警告：未检测到__file__变量，请确保您在.py文件中运行此脚本，并已手动切换到正确目录。")
except Exception as e:
    print(f"切换目录时发生错误: {e}")

#要装的库清单，在终端用pip来装：torch,pandas,numpy，transformers,sentence_transformers,scikit-learn,openai，python-dotenv，openpyxl！
#记得先装！
import time
import torch
import pandas as pd
import numpy as np
import json
from sentence_transformers import SentenceTransformer
from sklearn.neighbors import NearestNeighbors
from scipy.signal import find_peaks
import openpyxl
#  加载模型
cache_folder = './text2vec_model_cache' # 模型将保存在当前目录下的这个文件夹中
model_name = 'shibing624/text2vec-base-chinese'

print(f"正在从镜像站下载/加载模型 {model_name} 到本地目录 {cache_folder}...")#第一次下完
model = SentenceTransformer(model_name, cache_folder=cache_folder)
print("模型加载完成！")
# 读取 Excel
df = pd.read_excel("q.xlsx")
question_ids = df["index"].tolist()
questions = df["question"].tolist()

# 向量化
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = model.to(device)
embeddings = model.encode(questions, batch_size=32, device=device, show_progress_bar=True)
#这个batchsize 用64也可
np.save('question_embeddings.npy', embeddings)
embeddings_nd = np.load('question_embeddings.npy')

#保存 id-向量映射
id_vector_map = {str(qid): emb.tolist() for qid, emb in zip(question_ids, embeddings)}
print("向量化成功")

def data_perpare(embeddings_nd):
    print("检查是否已经标准化")
    if np.all(np.abs(np.mean(embeddings_nd,axis=0))< 0.1) and np.all(np.abs(np.std(embeddings_nd,axis=0))-1< 0.1):
        print("数据已标准化")
        return embeddings_nd
    else:
        print("数据未标准化,开始标准化")
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        embeddings_nd = scaler.fit_transform(embeddings_nd)
        print("数据已标准化")
        return embeddings_nd

embeddings_nd = data_perpare(embeddings_nd)

# 聚类
from sklearn.cluster import DBSCAN
from sklearn.cluster import AgglomerativeClustering

question_ids = list(id_vector_map.keys())
# 初始化 DBSCAN 模型
print("正在自动寻找DBSCAN的最优eps参数...")

def auto_eps(X, k=4, smooth_win=0.1):
    nn = NearestNeighbors(n_neighbors=k).fit(X)
    d = np.sort(nn.kneighbors(X)[0][:, -1])          # k-distance 排序
    der2 = np.convolve(np.gradient(np.gradient(d)), [1, -2, 1], 'same')
    w = max(3, int(smooth_win * len(d)))             # 窗宽 10%
    std = lambda x: np.std(x) if len(x) > 1 else 0
    score = [std(der2[i:i+w]) for i in range(len(d)-w)]
    elbow_idx = np.argmax(score) + w//2              # 最陡处
    return float(d[elbow_idx])

# 用法
eps = auto_eps(embeddings_nd) * 0.45

print(f"基于拐点检测找到的最优eps值: {eps:.4f}")
# 使用找到的最优eps初始化DBSCAN
dbscan = DBSCAN(eps=eps, min_samples=4)

# 对向量进行聚类
dbscan_labels = dbscan.fit_predict(embeddings)

# -1 代表噪声点，其余为簇标签（从0开始）
print("DBSCAN 聚类结果前20个:", dbscan_labels[:40])

# 获取所有有效簇（排除噪声 -1）
unique_labels = set(dbscan_labels)
unique_labels.discard(-1)  # 去掉噪声

# 计算每个簇的质心（即该簇所有向量的均值）
centroids = []
cluster_labels = []  # 每个质心对应的原始簇标签

for label in unique_labels:
    indices = np.where(dbscan_labels == label)[0]  # 该簇所有样本的索引
    cluster_vectors = embeddings[indices]#用来储存~某个簇的所有向量
    centroid = cluster_vectors.mean(axis=0)  # 质心
    centroids.append(centroid)
    cluster_labels.append(label)

centroids = np.array(centroids)

# 如果 DBSCAN 簇数 > 8，则用层次聚类合并
def auto_hierarchical_clustering(centroids, target_n=8, max_trials=20):#自动寻找最佳 distance_threshold，使层次聚类后的簇数最接近 target_n。
    
    # 先计算一个合理的阈值搜索范围
    # 用质心间的最小/最大距离作为边界
    from sklearn.metrics import pairwise_distances
    dist_mat = pairwise_distances(centroids)
    triu_dists = dist_mat[np.triu_indices_from(dist_mat, k=1)]
    low, high = triu_dists.min(), triu_dists.max()

    best_th, best_labels = None, None
    best_error = float('inf')

    # 二分搜索寻找最优 distance_threshold
    for _ in range(max_trials):
        mid = (low + high) / 2
        agg = AgglomerativeClustering(
            n_clusters=None,
            linkage='ward',
            distance_threshold=mid
        )
        labels = agg.fit_predict(centroids)
        n_clusters = len(set(labels))

        # 计算当前簇数与目标簇数的绝对误差
        error = abs(n_clusters - target_n)
        if error < best_error:
            best_error = error
            best_th = mid
            best_labels = labels
            # 提前终止：已精确匹配目标
            if n_clusters == target_n:
                break

        # 调整搜索方向
        if n_clusters > target_n:
            # 簇太多，需要合并 → 提高阈值
            low = mid
        else:
            # 簇太少，需要分裂 → 降低阈值
            high = mid

    print(f"[auto_hierarchical_clustering] 最终阈值={best_th:.4f}，"
          f"得到簇数={len(set(best_labels))}，目标簇数={target_n}")
    return best_labels, best_th


TARGET_SUPER_CLUSTERS = 8
if len(unique_labels) > TARGET_SUPER_CLUSTERS:
    # 自动寻找最佳阈值，使层次聚类后的簇数最接近 TARGET_SUPER_CLUSTERS
    final_labels, best_threshold = auto_hierarchical_clustering(centroids,target_n=TARGET_SUPER_CLUSTERS)
else:
    # 如果 DBSCAN 本身已满足数量要求，直接映射
    final_labels = list(range(len(unique_labels)))

# 构建原始簇 -> 最终超级簇的映射
original_to_final = {orig: final for orig, final in zip(cluster_labels, final_labels)}

# 将每个问题映射到最终超级簇
final_cluster_map = {}
for idx, label in enumerate(dbscan_labels):
    if label == -1:
        final_cluster_map[question_ids[idx]] = -1  # 噪声
    else:
        final_cluster_map[question_ids[idx]] = original_to_final[label]
final_cluster_map = {k: int(v) for k, v in final_cluster_map.items()}
# 保存最终映射
with open('final_cluster_map.json', 'w', encoding='utf-8') as f:
    json.dump(final_cluster_map, f, ensure_ascii=False, indent=2)

print("最终聚类映射已保存！")
print(f"最终超级簇数: {len(set(final_labels))}")
    
#调用api（终于）
from openai import OpenAI 
import os
from dotenv import load_dotenv
import time
import re

load_dotenv()# 加载 .env 文件，会从 .env 文件中读取变量，并把它们加载到系统的环境变量中
# 从环境变量中获取密钥
key = os.getenv("API_KEY")# os.getenv() 函数会安全地读取环境变量，如果变量不存在，它会返回 None
prompt1 = os.getenv("prompt1")
prompt2 = os.getenv("prompt2")
prompt3_text = os.getenv("prompt3")
client = OpenAI(
    api_key = key,
    base_url="https://api.moonshot.cn/v1",
)
if key:
    print("成功读取到API密钥！")    
else:
    print("错误：未能读取到API密钥，请检查 .env 文件。")

f_final_cluster_map = {}
for qid, cid in final_cluster_map.items():
    if cid not in f_final_cluster_map:
        f_final_cluster_map[cid] = []
    f_final_cluster_map[cid].append(qid)

intent_map = {}# 创建一个字典来存储每个簇的关注点分析结果 格式: {簇ID: "LLM返回的意图字符串"}
analyzed_clusters = set()
# 遍历每一个超级簇
sorted_final_labels = sorted(final_labels)
for cluster_id in sorted_final_labels:
    if cluster_id in analyzed_clusters:
        continue
    print(f"--- 正在分析超级簇 {cluster_id} 的关注点 ---")
    analyzed_clusters.add(cluster_id)

    # 提取当前簇的所有原始问题文本
    org_text = []
    question_list = f_final_cluster_map[cluster_id]
    for qid in question_list:
        question_text = df[df['index'] == int(qid)]['question'].values
        if len(question_text) > 0:
            org_text.append(f"{len(org_text)+1}. {question_text[0]}")
      
    #  构建发送给LLM的Prompt
    full_user_prompt = prompt2 + "\n".join(org_text)# 我们将 .env 文件中的 prompt2 作为模板，然后把问题列表拼接到后面   
    #  调用API进行关注点提取
    try:
        print(f"簇 {cluster_id} 正在请求LLM分析...")
        completion = client.chat.completions.create(
            model="kimi-k2-0905-preview", # 使用你的模型
            messages=[
                {"role": "system", "content": prompt1}, # prompt1 是系统指令，定义角色和任务
                {"role": "user", "content": full_user_prompt} # prompt2+问题列表 是用户输入
            ],
            temperature=0.2, 
        )
        intent_result = completion.choices[0].message.content
        intent_map[cluster_id] = intent_result
        print(f"簇 {cluster_id} 关注点分析成功！")
        print(f"分析结果摘要: {intent_result[:50]}...") # 打印前50个字符预览
        

    except Exception as e:
        print(f"错误：簇 {cluster_id} 关注点分析失败: {e}")
        intent_map[cluster_id] = f"关注点分析失败: {str(e)}"

print("\n所有簇的关注点分析完成")

# 根据上一步提取的关注点，为每个簇生成25个新的问题。
# 创建一个字典来存储每个簇生成的新问题
generated_questions_map = {}# 格式: {簇ID: ["新问题1", "新问题2", ...]}
print("\n开始根据关注点生成新问题...")
print("（胜利就在眼前！hhhh）")

# 遍历刚刚存储的关注点映射
for cluster_id, intent_string in intent_map.items():
    # 跳过分析失败的簇
    if "失败" in intent_string:
        print(f"跳过簇 {cluster_id}，因为其关注点分析失败。")
        continue
        
    print(f"--- 正在为簇 {cluster_id} 生成新问题 ---")
    
    # 构建问题生成的Prompt
    prompt3 = prompt3_text + intent_string
    
    # b. 调用API生成问题
    try:
        print(f"正在请求LLM为簇 {cluster_id} 生成问题...")
        print("可能会比较久，大概1min，耐心等等（都到这里了doge）")
        completion = client.chat.completions.create(
            model="kimi-k2-0711-preview",
            messages=[
                {"role": "user", "content": prompt3}
            ],
            temperature=0.5, 
        )
        generated_text = completion.choices[0].message.content
        print(generated_text)
        try:
            response_data = json.loads(generated_text)
            # 从 JSON 中提取问题列表
            questions_list = response_data.get("questions", [])
            keywords = response_data.get("keywords", [])
            generated_questions_map[cluster_id] = {
            "questions": questions_list,}
            print(f"簇 {cluster_id} 成功生成了 {len(questions_list)} 个问题")
        except json.JSONDecodeError:
            print(f"警告：簇 {cluster_id} 的响应不是有效的 JSON 格式")
   
    except Exception as e:
        print(f"错误：为簇 {cluster_id} 生成问题失败: {e}")
        generated_questions_map[cluster_id] = [] # 失败则存入空列表

print("\n所有簇的问题生成完成！")
print("\n正在整理数据并保存到Excel文件...")

output_rows = []# 准备一个列表，用于存储DataFrame的每一行数据

for cluster_id, data in generated_questions_map.items():
    intent_description = intent_map.get(cluster_id, "无意图描述")
    questions_list = data.get("questions", [])   
    for question in questions_list:
        output_rows.append({
            "cluster_id": cluster_id,
            "main_intent": intent_description,
            "generated_question": question,
        })

df_output = pd.DataFrame(output_rows)# 创建DataFrame
output_filename = "generated_question_bank.xlsx"
df_output.to_excel(output_filename, index=False, engine='openpyxl')# 保存为Excel文件
df_output.to_csv("question_bank.csv", index=True, encoding='utf-8-sig')
print(f"最终问题库已成功保存到文件: {output_filename}")
#文件包含三列：cluster_id (所属簇), main_intent (簇意图), generated_question (生成的问题)


