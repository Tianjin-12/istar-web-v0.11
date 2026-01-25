AI可见度评估系统 - 订单处理流程优化技术文档
1. 项目架构概述
1.1 技术栈
| 层级 | 技术组件 | 版本 |
| Web框架 | Django | 4.2 |
| 数据库 | PostgreSQL | 15 |
| 消息队列 | Redis | 7-alpine |
| 任务队列 | Celery | 5.3 |
| 任务调度 | django-celery-beat | 2.5 |
| 数据可视化 | Dash + Plotly | 2.14+5.0 |
| 网络爬虫 | Playwright | 1.40+ |
| NLP引擎 | SentenceTransformer | 2.2 |
| 机器学习 | scikit-learn | 1.3 |
| LLM客户端 | OpenAI SDK | 1.0 |
| Web服务器 | Gunicorn | 21.0 |
1.2 部署架构
│  服务器直接部署（基于 Supervisor）
│  进程管理: Supervisor
│  Services:
│  • PostgreSQL 15 (端口 5432) - 系统服务
│  • Redis 7 (端口 6380) - 系统服务
│  • Gunicorn Web (端口 8000) - Supervisor 管理
│  • Celery Worker - Supervisor 管理（多进程）
│  • Celery Beat 节点1 (RedBeat 主节点/备节点) - Supervisor 管理
│  • Celery Beat 节点2 (RedBeat 备节点) - Supervisor 管理
│  • Flower (监控面板，端口 5555) - Supervisor 管理
│  • 健康检查脚本 - Supervisor 管理
1.3 数据模型
现有模型：
- Order: 订单（用户、关键词、品牌、状态、任务ID）
- Notification: 通知（用户、订单、消息、已读状态）
- Mention_percentage: 提及率统计（品牌、关键词、各类提及率）
需要新增的模型：
- ZhihuQuestion: 知乎问题缓存
- QuestionBank: 问题库缓存
- AIAnswer: AI回答缓存
- AILink: 回答中的链接
- QuestionScore: 问题评分缓存
- TaskLog: 任务执行日志
---
2. 核心优化策略
2.1 问题分析
当前流程缺陷：
- 每个订单独立执行4个阶段，大量重复工作
- 相同关键词的订单重复搜索、构建、收集
- LLM API成本高、资源浪费严重
优化目标：
- 以关键词为粒度进行缓存和复用
- 减少冗余工作，提升处理效率
- 降低API成本和资源占用
2.2 关键词级缓存策略
2.2.1 缓存层级设计
第一层：知乎问题（7天）
  • 输入：关键词
  • 输出：问题列表（50-100个）
  • 缓存：ZhihuQuestion 表
  • 触发条件：每7天更新一次
第二层：问题库（7天）
  • 输入：知乎问题列表
  • 输出：聚类后的问题库（8簇，每簇25个问题）
  • 缓存：QuestionBank 表
  • 触发条件：每7天更新一次
第三层：AI回答（1天） 每日更新
  • 输入：问题库
  • 输出：AI回答列表（200个问题×回答）
  • 缓存：AIAnswer, AILink 表
  • 触发条件：每天凌晨更新
第四层：问题评分（1天）
  • 输入：AI回答
  • 输出：问题评分（0-4分）
  • 缓存：QuestionScore 表
  • 触发条件：每天凌晨更新
2.2.2 任务执行流程
优化后流程（关键词级共享）：
例子：对关键词"蓝牙耳机"的所有订单:
  ├─ Order 1: Nike + 蓝牙耳机
  ├─ Order 2: Sony + 蓝牙耳机
  └─ Order 3: Bose + 蓝牙耳机
执行流程:
  1. 检查知乎问题缓存（7天有效）
     → 无缓存：搜索知乎 → 存入 ZhihuQuestion
     → 有缓存：直接使用
  2. 检查问题库缓存（7天有效）
     → 无缓存：向量化 → 聚类 → 生成问题 → 存入 QuestionBank
     → 有缓存：直接使用
  3. 检查AI回答缓存（1天有效）每日强制更新
     → 每天凌晨：重新收集所有回答 → 存入 AIAnswer, AILink
     → 其他时间：使用缓存
  4. 对每个订单进行Summary分析（每日强制更新）
     → 使用当天的AI回答和评分
     → 统计品牌/链接提及率
     → 存入 Mention_percentage 表
3. 数据库设计
3.1 新增表结构
3.1.1 知乎问题缓存表
表名: mvp_zhihuquestion
| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| id | BigAutoField | 主键 | PK |
| keyword | CharField(255) | 关键词 | IDX |
| question_text | TextField | 问题内容 | - |
| question_id | IntegerField | 问题序号 | IDX |
| created_at | DateTimeField | 创建时间 | IDX |
索引设计:
CREATE INDEX idx_zhihu_keyword_created ON mvp_zhihuquestion(keyword, created_at DESC);
CREATE INDEX idx_zhihu_qid ON mvp_zhihuquestion(question_id);
数据保留: 7天，过期自动删除
---
3.1.2 问题库缓存表
表名: mvp_questionbank
| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| id | BigAutoField | 主键 | PK |
| keyword | CharField(255) | 关键词 | IDX |
| cluster_id | IntegerField | 聚类ID | IDX |
| main_intent | TextField | 聚类意图 | - |
| generated_question | TextField | 生成的问题 | - |
| created_at | DateTimeField | 创建时间 | IDX |
索引设计:
CREATE INDEX idx_qb_keyword_cluster ON mvp_questionbank(keyword, cluster_id);
CREATE INDEX idx_qb_created ON mvp_questionbank(created_at DESC);
数据保留: 7天，过期自动删除
---
3.1.3 AI回答缓存表
表名: mvp_aianswer
| 字段名 | 类型 | 说明 | 索引 |
| id | BigAutoField | 主键 | PK |
| keyword | CharField(255) | 关键词 | IDX |
| question_id | CharField(100) | 问题ID | IDX |
| question_text | TextField | 问题内容 | - |
| answer_text | TextField | AI回答 | - |
| answer_date | DateField | 回答日期 | IDX |
| created_at | DateTimeField | 创建时间 | IDX |
索引设计:
CREATE INDEX idx_ai_keyword_qid ON mvp_aianswer(keyword, question_id);
CREATE INDEX idx_ai_date ON mvp_aianswer(answer_date DESC);
数据保留: 1天，过期自动删除（每天凌晨清空重写）
---
3.1.4 AI回答链接表
表名: mvp_ailink
| 字段名 | 类型 | 说明 | 索引 |
| id | BigAutoField | 主键 | PK |
| answer_id | ForeignKey | 关联AIAnswer | IDX |
| link_url | TextField | 链接URL | - |
| created_at | DateTimeField | 创建时间 | - |
索引设计:
CREATE INDEX idx_link_answer ON mvp_ailink(answer_id);
数据保留: 与AI回答同步删除
---
3.1.5 问题评分缓存表
表名: mvp_questionscore
| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| id | BigAutoField | 主键 | PK |
| keyword | CharField(255) | 关键词 | IDX |
| question_id | CharField(100) | 问题ID | IDX |
| score | IntegerField | 评分(0-4) | IDX |
| answer_date | DateField | 评分日期 | IDX |
| created_at | DateTimeField | 创建时间 | IDX |
索引设计:
CREATE INDEX idx_score_keyword_qid ON mvp_questionscore(keyword, question_id);
CREATE INDEX idx_score_date ON mvp_questionscore(answer_date DESC);
数据保留: 1天，过期自动删除
---
3.1.6 任务执行日志表
表名: mvp_tasklog
| 字段名 | 类型 | 说明 | 索引 |
|--------|------|------|------|
| id | BigAutoField | 主键 | PK |
| order_id | IntegerField | 订单ID | IDX |
| task_type | CharField(50) | 任务类型 | IDX |
| status | CharField(20) | 状态 | IDX |
| retry_count | IntegerField | 重试次数 | - |
| error_message | TextField | 错误信息 | - |
| started_at | DateTimeField | 开始时间 | IDX |
| completed_at | DateTimeField | 完成时间 | IDX |
| duration | IntegerField | 执行时长(秒) | - |
索引设计:
CREATE INDEX idx_tasklog_order ON mvp_tasklog(order_id);
CREATE INDEX idx_tasklog_status ON mvp_tasklog(status);
CREATE INDEX idx_tasklog_started ON mvp_tasklog(started_at DESC);
数据保留: 1个月，过期归档
---
3.2 现有模型扩展
3.2.1 Order 模型扩展
新增字段:
class Order(models.Model):
    # ... 现有字段 ...
    
    # 新增：任务追踪
    current_stage = models.CharField(max_length=50, blank=True, null=True, verbose_name="当前阶段")
    progress_percentage = models.IntegerField(default=0, verbose_name="进度百分比")
    last_error = models.TextField(blank=True, null=True, verbose_name="最后错误")
    retry_count = models.IntegerField(default=0, verbose_name="重试次数")
    is_cached = models.BooleanField(default=False, verbose_name="是否使用缓存")
---
4. 任务流程设计
4.1 任务层级架构
│         Celery Beat 定时调度           
│    每天凌晨 00:00 触发                
                  │
                  ▼
│   Stage 1: 按关键词分组订单            
│   group_orders_by_keyword()            
               
        │         │         │
        ▼         ▼         ▼
   [关键词1]   [关键词2]   [关键词N]
        │         │         │
        ▼         ▼         ▼
│   Stage 2: 关键词级任务链              
│   chain(check_cache()                   
│     search_questions()  [7天缓存]       
│     build_question_bank() [7天缓存]
│     collect_ai_answers() [每日更新]
│     score_questions() [每日更新] ) 
                  ▼
│   Stage 3: 批量分析订单                
│   analyze_all_orders(orders)              
│     ├─ Order 1: summary(brand, link)    
│     ├─ Order 2: summary(brand, link)    
│     └─ Order N: summary(brand, link)      │

4.2 任务定义
4.2.1 任务列表
| 任务名 | 功能 | 超时时间 | 重试次数 | 队列 |
|--------|------|----------|----------|------|
| group_orders_by_keyword | 订单分组 | 60秒 | 2 | fast |
| check_cache_status | 检查缓存 | 30秒 | 1 | fast |
| search_questions | 搜索知乎 | 600秒 | 2 | slow |
| build_question_bank | 构建问题库 | 1200秒 | 2 | ml |
| collect_ai_answers | 收集AI回答 | 3600秒 | 2 | browser |
| score_questions | 问题评分 | 600秒 | 2 | llm |
| analyze_all_orders | 批量分析 | 1800秒 | 2 | normal |
| cleanup_old_data | 数据清理 | 1800秒 | 1 | maintenance |
| archive_old_data | 数据归档 | 3600秒 | 1 | maintenance |



4.2.2 任务队列设计
| 队列名 | 并发数 | 用途 |
|--------|--------|------|
| fast | 1 | 快速任务（状态更新、缓存检查） |
| slow | 2 | 慢速任务（搜索、模型） |
| ml | 3 | 机器学习任务（问题库） |
| browser | 3 | 浏览器任务（AI回答收集） |
| llm | 2 | LLM API任务（评分） |
| normal | 2 | 普通任务（批量分析） |
| maintenance | 1 | 维护任务（清理、归档） |
---
4.3 失败处理策略
4.3.1 重试机制
重试规则:
- 最大重试次数：2次
- 重试间隔：指数退避（60秒、120秒）
- 重试后仍失败：标记为 failed
重试流程:
任务执行 → 失败
  → 检查 retry_count < 2
     → True: retry_count += 1，延迟重试
     → False: 标记订单为 failed，记录错误
4.3.2 错误处理
错误分类:
1. 临时性错误（网络超时、API限流）: 自动重试
2. 业务错误（参数错误、逻辑错误）: 记录错误，标记失败
3. 系统错误（内存不足、浏览器崩溃）: 标记失败，发送告警
错误记录:
- 记录到 TaskLog 表
- 记录到 Order.last_error 字段
- 发送通知给用户
---
4.4 数据保留和归档策略
4.4.1 数据保留周期
| 数据类型 | 保留周期 | 清理频率 | 归档策略 |
|----------|----------|----------|----------|
| 知乎问题 | 7天 | 每天 | 删除 |
| 问题库 | 7天 | 每天 | 删除 |
| AI回答 | 1天 | 每天 | 删除 |
| 问题评分 | 1天 | 每天 | 删除 |
| 任务日志 | 1个月 | 每周 | 归档 |
| 提及率数据 | 永久 | - | 不清理 |
4.4.2 归档机制
归档策略:
1. 数据库归档:
   - 将 TaskLog 表中超过1个月的数据导出为 CSV
   - 存储到 /var/archive/tasks/YYYY-MM.csv
   - 从数据库中删除已归档记录
2. 文件清理:
   - 删除超过1个月的归档文件
   - 定期清理 Redis 缓存
归档任务:
- 执行时间：每周日凌晨 02:00
- 任务名：archive_old_data
- 执行方式：Celery Beat 定时触发

创建归档目录:
```bash
sudo mkdir -p /var/archive/tasks
sudo chown www-data:www-data /var/archive/tasks
```
---
4.5 分布式 Beat 高可用调度
4.5.1 单点问题分析
当前架构问题:
- Celery Beat 为单点调度器
- 调度器崩溃后，定时任务无法执行
- 需要手动干预恢复
4.5.2 解决方案：celery-redBeat
技术选型:
- 库：celery-redbeat
- 原理：调度状态存储在 Redis，支持多节点
- 优势：自动故障转移，无单点故障
4.5.3 配置方案
安装依赖:
```bash
pip install celery-redbeat
```
Django settings 配置:
```python
# 使用 RedBeat 替代默认调度器
CELERY_BEAT_SCHEDULER = 'redbeat.RedBeatScheduler'
# Redis 连接（使用现有 Redis 实例）
CELERY_REDBEAT_REDIS_URL = 'redis://redis:6380/1'
# 锁超时时间（秒）
CELERY_REDBEAT_LOCK_TIMEOUT = 30
```
4.5.4 部署架构
```
┌─────────────────────────────────────────┐
│         服务器部署（Supervisor）           │
├─────────────────────────────────────────┤
│  Beat 节点1    Beat 节点2                │
│  (主/备)       (备节点)                   │
│       └──────────┬──────────┘             │
│                  ▼                        │
│            Redis (存储调度状态)           │
│            - 锁机制                        │
│            - 选主算法                      │
│            - 自动故障转移                   │
└─────────────────────────────────────────┘
```
4.5.5 运行方式
Supervisor 配置文件（/etc/supervisor/conf.d/celery.conf）:
```ini
[program:celery-beat-1]
command=/path/to/venv/bin/celery -A myproject beat -l info -S redbeat.RedBeatScheduler --hostname=beat1@%%h
directory=/path/to/myproject
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
environment=CELERY_BROKER_URL="redis://localhost:6380/0",CELERY_REDBEAT_REDIS_URL="redis://localhost:6380/1"
stdout_logfile=/var/log/celery/beat1.log
stderr_logfile=/var/log/celery/beat1.err

[program:celery-beat-2]
command=/path/to/venv/bin/celery -A myproject beat -l info -S redbeat.RedBeatScheduler --hostname=beat2@%%h
directory=/path/to/myproject
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
environment=CELERY_BROKER_URL="redis://localhost:6380/0",CELERY_REDBEAT_REDIS_URL="redis://localhost:6380/1"
stdout_logfile=/var/log/celery/beat2.log
stderr_logfile=/var/log/celery/beat2.err
```

启动命令:
```bash
# 重新加载 Supervisor 配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动 Beat 节点
sudo supervisorctl start celery-beat-1
sudo supervisorctl start celery-beat-2

# 查看状态
sudo supervisorctl status
```
工作原理:
- 多个 Beat 节点同时运行
- 通过 Redis 锁竞争选主
- 主节点执行调度，备节点待命
- 主节点故障后，自动切换到备节点
- 调度任务不重复执行
4.5.6 监控指标
- Redis 中查看当前主节点：`GET redbeat:master`
- 查看调度状态：`KEYS redbeat:*`
- 告警：锁超时（主节点未按时更新）
---
4.6 健康检查和自愈机制
4.6.1 健康检查设计
检查层级:
1. Celery Worker 健康检查
   - 检查命令：`celery -A myproject inspect ping`
   - 检查频率：30秒
   - 健康标准：返回 `{'ok': 'pong'}`
2. Celery Beat 健康检查
   - 检查命令：`redis-cli GET redbeat:master`
   - 检查频率：30秒
   - 健康标准：锁存在且时间戳未过期
3. Redis 健康检查
   - 检查命令：`redis-cli PING`
   - 检查频率：10秒
   - 健康标准：返回 `PONG`
4. PostgreSQL 健康检查
   - 检查命令：`psql -h db -U postgres -c "SELECT 1"`
   - 检查频率：10秒
   - 健康标准：无错误返回
4.6.2 自愈策略
Supervisor 自动重启配置:
```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A myproject worker -l info --hostname=worker@%%h
directory=/path/to/myproject
user=www-data
numprocs=5
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
exitcodes=0,1
environment=CELERY_BROKER_URL="redis://localhost:6380/0",CELERY_RESULT_BACKEND="redis://localhost:6380/1"
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker.err
```

自愈机制说明:
- `autorestart=true`: 进程退出后自动重启
- `startsecs=10`: 进程启动后等待10秒才认为成功
- `stopwaitsecs=60`: 停止命令发出后等待60秒才强制终止
- `exitcodes=0,1`: 只有退出码为0或1时才重启
- `numprocs=5`: 启动5个 worker 进程

systemd 服务配置（PostgreSQL 和 Redis）:
```ini
# /etc/systemd/system/postgresql.service
[Unit]
Description=PostgreSQL database server
After=network.target

[Service]
Type=notify
User=postgres
ExecStart=/usr/lib/postgresql/15/bin/postgres -D /var/lib/postgresql/15/main
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/redis.service
[Unit]
Description=Redis In-Memory Data Store
After=network.target

[Service]
Type=notify
User=redis
ExecStart=/usr/local/bin/redis-server /etc/redis/redis.conf
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```
4.6.3 告警触发条件
| 检查项 | 触发条件 | 严重级别 | 恢复动作 |
|--------|----------|----------|----------|
| Worker 健康检查 | 连续3次失败 | 高 | 自动重启 |
| Beat 主节点 | 锁超时5分钟 | 高 | 备节点自动接管 |
| Redis 连接 | 连续5次失败 | 高 | 自动重启 |
| PostgreSQL 连接 | 连续5次失败 | 高 | 自动重启 |

4.6.4 监控脚本（可选）
创建健康检查脚本 `scripts/health_monitor.sh`:
```bash
#!/bin/bash
# 每30秒检查一次
CELERY_CMD="/path/to/venv/bin/celery -A myproject"
LOG_DIR="/var/log/health_monitor"

mkdir -p $LOG_DIR

while true; do
  # 检查 Worker 状态
  if ! $CELERY_CMD inspect ping &> /dev/null; then
    echo "[$(date)] [ALERT] Celery Worker is not responding!" >> $LOG_DIR/monitor.log
    # 可以触发钉钉/邮件通知
  fi

  # 检查 Beat 主节点
  MASTER=$(redis-cli -p 6380 GET redbeat:master)
  if [ -z "$MASTER" ]; then
    echo "[$(date)] [ALERT] No active Beat master found!" >> $LOG_DIR/monitor.log
  fi

  # 检查 Supervisor 状态
  if ! supervisorctl status celery-worker &> /dev/null; then
    echo "[$(date)] [ALERT] Celery Worker not running!" >> $LOG_DIR/monitor.log
    supervisorctl start celery-worker
  fi

  sleep 30
done
```

添加到 Supervisor 管理:
```ini
[program:health-monitor]
command=/bin/bash /path/to/scripts/health_monitor.sh
user=www-data
autostart=true
autorestart=true
stdout_logfile=/var/log/health-monitor.log
stderr_logfile=/var/log/health-monitor.err
```
---
4.7 熔断机制
4.7.1 熔断器设计原理
熔断器状态机:
- Closed（关闭）：正常状态，允许请求通过
- Open（开启）：故障状态，快速失败
- Half-Open（半开）：试探状态，允许少量请求
状态转换:
```
Closed ──(连续失败N次)──> Open
Open ──(超时时间后)──> Half-Open
Half-Open ──(请求成功)──> Closed
Half-Open ──(请求失败)──> Open
```
4.7.2 集成方案
安装依赖:
```bash
pip install pybreaker
```
配置熔断器（settings.py）:
```python
import pybreaker

# LLM API 熔断器
llm_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=3,              # 连续失败3次后熔断
    reset_timeout=60,        # 60秒后进入半开状态
    name='llm_api'
)

# 知乎搜索熔断器
zhihu_search_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name='zhihu_search'
)

# Playwright 熔断器
playwright_breaker = pybreaker.CircuitBreaker(
    fail_max=2,
    reset_timeout=60,
    name='playwright'
)
```
使用示例（tasks.py）:
```python
from pybreaker import CircuitBreakerError
from myproject.settings import llm_circuit_breaker

@celery.task(bind=True, max_retries=3)
@llm_circuit_breaker
def call_llm_api(self, text):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": text}],
            timeout=30
        )
        return response.choices[0].message.content
    except CircuitBreakerError:
        # 熔断器开启，快速失败
        raise self.retry(countdown=60)
    except Exception as e:
        # 记录失败
        llm_circuit_breaker.call_failed()
        raise
```
4.7.3 熔断策略配置
| 服务类型 | 失败阈值 | 恢复超时 | 说明 |
|----------|----------|----------|------|
| LLM API | 3次 | 60秒 | 防止持续调用浪费额度 |
| 知乎搜索 | 3次 | 30秒 | 防止被反爬限制 |
| Playwright | 2次 | 60秒 | 浏览器崩溃时快速恢复 |
| 数据库 | 5次 | 10秒 | 数据库故障时快速切换 |
4.7.4 熔断事件监控
监听熔断器事件（settings.py）:
```python
class CircuitBreakerListener:
    def before_call(self, cb, func, *args, **kwargs):
        print(f"[熔断器] 调用函数: {func.__name__}")

    def success(self, cb, func, *args, **kwargs):
        print(f"[熔断器] 调用成功: {func.__name__}")

    def failure(self, cb, func, exc, *args, **kwargs):
        print(f"[熔断器] 调用失败: {func.__name__}, 错误: {exc}")

    def state_change(self, cb, old_state, new_state):
        print(f"[熔断器] 状态变化: {old_state} -> {new_state}")

llm_circuit_breaker.add_listener(CircuitBreakerListener())
```
4.7.5 告警配置
| 事件 | 严重级别 | 告警方式 |
|------|----------|----------|
| 熔断器开启 | 高 | 钉钉/邮件 |
| 熔断器恢复 | 中 | 钉钉/邮件 |
| 半开状态失败 | 中 | 钉钉/邮件 |
4.7.6 熔断器仪表板（Django Admin）
新增熔断器状态页面:
```python
# admin.py
from django.contrib import admin
from pybreaker import CircuitBreaker

@admin.register
class CircuitBreakerAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'failure_count', 'last_failure_time']
    readonly_fields = ['state', 'failure_count', 'last_failure_time']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
```
---
4.8 断路续传机制
4.8.1 进度记录设计
核心思想:
- 记录任务处理进度到数据库
- 任务中断后从断点恢复
- 避免重复处理已完成的步骤
4.8.2 进度数据模型
扩展现有 TaskLog 模型（3.1.6 节已定义），新增进度字段:
```python
class TaskLog(models.Model):
    # ... 现有字段 ...

    # 新增：进度跟踪字段
    progress_checkpoint = models.JSONField(blank=True, null=True, verbose_name="进度检查点")
    processed_items = models.IntegerField(default=0, verbose_name="已处理数量")
    total_items = models.IntegerField(default=0, verbose_name="总数量")
    last_checkpoint_time = models.DateTimeField(blank=True, null=True, verbose_name="最后检查点时间")
```
进度数据结构（JSON）:
```json
{
  "stage": "collect_ai_answers",
  "keyword": "蓝牙耳机",
  "completed_questions": ["qid_001", "qid_002", "qid_003"],
  "current_question": "qid_004",
  "question_count": 200,
  "started_at": "2025-01-25T00:00:00Z"
}
```
4.8.3 断点恢复实现
任务任务模板（tasks.py）:
```python
from django.utils import timezone
from mvp.models import TaskLog

@celery.task(bind=True, max_retries=3)
def collect_ai_answers(self, keyword, order_ids):
    # 创建/获取任务日志
    task_log, created = TaskLog.objects.get_or_create(
        task_type='collect_ai_answers',
        order_id__in=order_ids,
        defaults={
            'status': 'running',
            'started_at': timezone.now()
        }
    )

    try:
        # 检查是否有断点
        checkpoint = task_log.progress_checkpoint or {}

        # 获取问题库
        questions = get_question_bank(keyword)

        # 过滤已处理的问题
        completed_questions = set(checkpoint.get('completed_questions', []))
        pending_questions = [q for q in questions if q['id'] not in completed_questions]

        task_log.total_items = len(questions)
        task_log.processed_items = len(completed_questions)
        task_log.save()

        # 处理剩余问题
        for i, question in enumerate(pending_questions, 1):
            try:
                # 收集回答
                answer = scrape_ai_answer(question['url'])
                save_ai_answer(keyword, question['id'], answer)

                # 更新进度
                completed_questions.add(question['id'])
                checkpoint.update({
                    'completed_questions': list(completed_questions),
                    'current_question': question['id'],
                    'question_count': len(questions)
                })
                task_log.progress_checkpoint = checkpoint
                task_log.processed_items = len(completed_questions)
                task_log.last_checkpoint_time = timezone.now()
                task_log.save()

                # 每处理10个问题更新一次
                if i % 10 == 0:
                    self.update_state(
                        state='PROGRESS',
                        meta={'progress': len(completed_questions), 'total': len(questions)}
                    )

            except Exception as e:
                # 单个问题失败不影响整体
                log_error(question['id'], e)
                continue

        # 任务完成
        task_log.status = 'completed'
        task_log.completed_at = timezone.now()
        task_log.progress_checkpoint = None  # 清理断点
        task_log.save()

    except Exception as e:
        # 任务失败，保留断点
        task_log.status = 'failed'
        task_log.error_message = str(e)
        task_log.save()
        raise
```
4.8.4 自动恢复策略
Celery Beat 定时任务配置:
```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'check-stalled-tasks': {
        'task': 'mvp.tasks.check_stalled_tasks',
        'schedule': crontab(minute='*/5'),  # 每5分钟检查一次
    }
}
```
停滞任务检查（tasks.py）:
```python
@celery.task
def check_stalled_tasks():
    # 查找超过1小时未更新的失败任务
    stalled_threshold = timezone.now() - timezone.timedelta(hours=1)

    stalled_tasks = TaskLog.objects.filter(
        status='failed',
        updated_at__lt=stalled_threshold,
        retry_count__lt=3
    )

    for task in stalled_tasks:
        # 检查是否有断点
        if task.progress_checkpoint:
            print(f"恢复停滞任务: {task.id}")
            # 根据任务类型恢复
            if task.task_type == 'collect_ai_answers':
                collect_ai_answers.retry(
                    args=[task.progress_checkpoint['keyword']],
                    countdown=60
                )
            elif task.task_type == 'build_question_bank':
                build_question_bank.retry(
                    args=[task.progress_checkpoint['keyword']],
                    countdown=60
                )

            # 更新重试次数
            task.retry_count += 1
            task.save()
```
4.8.5 手动重试接口
Django Admin 自定义动作（admin.py）:
```python
from django.contrib import admin
from mvp.models import TaskLog

@admin.register(TaskLog)
class TaskLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'task_type', 'status', 'progress_percentage', 'retry_count']
    list_filter = ['status', 'task_type']
    actions = ['retry_failed_tasks']

    def retry_failed_tasks(self, request, queryset):
        count = 0
        for task in queryset.filter(status='failed'):
            if task.progress_checkpoint:
                # 触发恢复
                from mvp.tasks import TASK_MAP
                task_func = TASK_MAP[task.task_type]
                task_func.retry(args=[task.progress_checkpoint['keyword']])
                task.status = 'pending'
                task.retry_count += 1
                task.save()
                count += 1
        self.message_user(request, f"已恢复 {count} 个任务")

    retry_failed_tasks.short_description = "恢复选中的失败任务"
```
4.8.6 进度查询 API
新增 API 端点（views.py）:
```python
from rest_framework.views import APIView
from rest_framework.response import Response
from mvp.models import TaskLog

class TaskProgressView(APIView):
    def get(self, request, task_id):
        task_log = TaskLog.objects.get(id=task_id)
        progress = task_log.progress_checkpoint or {}

        return Response({
            'task_id': task_id,
            'status': task_log.status,
            'progress': task_log.processed_items,
            'total': task_log.total_items,
            'percentage': int(task_log.processed_items / task_log.total_items * 100) if task_log.total_items > 0 else 0,
            'current_item': progress.get('current_item'),
            'last_updated': task_log.last_checkpoint_time
        })
```
路由配置（urls.py）:
```python
from django.urls import path
from mvp.views import TaskProgressView

urlpatterns = [
    path('api/task/<int:task_id>/progress/', TaskProgressView.as_view()),
]
```
---
5. 监控系统设计
5.1 监控工具选型
推荐方案: Flower
选择理由:
- Celery 官方推荐的实时监控工具
- 开源免费，功能完整
- 支持任务状态、执行时间、worker状态监控
- 提供Web界面，使用简单
备选方案:
- Prometheus + Grafana: 适合大型系统，配置复杂
- Sentry: 适合错误监控，需要付费
- Django Debug Toolbar: 仅适合开发环境
---
5.2 Flower 集成方案
5.2.1 部署架构
┌─────────────────────────────────────┐
│         Docker Compose              │
├─────────────────────────────────────┤
│  Services:                        │
│  • flower (新增)                  │
│    - 映射端口: 5555:5555          │
│    - 连接 Redis: redis:6380       │
│    - 基础认证 (可选)             │
└─────────────────────────────────────┘
docker-compose.yml 配置:
flower:
  build: .
  command: celery -A myproject flower --port=5555
  ports:
    - "5555:5555"
  depends_on:
    - redis
  environment:
    - CELERY_BROKER_URL=redis://redis:6380/0
5.2.2 访问地址
- 本地环境: http://localhost:5555
- 生产环境: https://istar-geo.com/flower
5.2.3 监控指标
任务维度:
- 任务执行状态（成功/失败/重试/进行中）
- 任务执行时间（平均、最大、最小）
- 任务队列长度（待处理任务数）
- 任务失败率（失败任务/总任务）
Worker维度:
- Worker 在线状态
- Worker 负载情况（CPU/内存）
- Worker 任务处理速度
- Worker 心跳检测
系统维度:
- Redis 内存使用率
- Redis 连接数
- 数据库连接数
- 磁盘空间使用率
---
5.3 自定义监控指标
5.3.1 Django Admin 扩展
新增管理页面:
/admin/mvp/order/          # 订单管理（增强版）
  • 显示实时进度
  • 显示任务日志
  • 手动重试失败任务
/admin/mvp/tasklog/       # 任务日志（新增）
  • 查看所有任务执行记录
  • 按状态/时间/订单筛选
  • 导出日志为 CSV
/admin/mvp/statistics/     # 统计概览（新增）
  • 今日任务总数
  • 今日成功率
  • 今日平均处理时间
  • 关键词缓存命中率
5.3.2 API 监控端点
新增 API:
- /api/monitor/stats/: 系统统计信息
- /api/monitor/orders/:id/: 订单实时进度
- /api/monitor/tasks/running/: 正在运行的任务
- /api/monitor/tasks/failed/: 失败的任务
- /api/task/:id/progress/: 任务进度详情（断点续传）
- /api/monitor/circuit-breakers/: 熔断器状态
- /api/monitor/beat-master/: 当前 Beat 主节点
5.3.3 熔断器监控端点
返回格式:
```json
{
  "llm_api": {
    "state": "closed",
    "failure_count": 0,
    "last_failure_time": null,
    "next_attempt_time": null
  },
  "zhihu_search": {
    "state": "open",
    "failure_count": 3,
    "last_failure_time": "2025-01-25T10:30:00Z",
    "next_attempt_time": "2025-01-25T10:31:00Z"
  },
  "playwright": {
    "state": "half-open",
    "failure_count": 2,
    "last_failure_time": "2025-01-25T10:28:00Z",
    "next_attempt_time": "2025-01-25T10:29:00Z"
  }
}
```
---
5.4 告警机制
5.4.1 告警触发条件
| 告警类型 | 触发条件 | 严重级别 |
|----------|----------|----------|
| 任务失败 | 单个任务重试2次后仍失败 | 中 |
| Worker离线 | Worker 心跳超时5分钟 | 高 |
| 队列积压 | 队列长度 > 100 | 中 |
| API限流 | LLM API 返回429错误 | 高 |
| 数据库异常 | 数据库连接失败 | 高 |
| Redis异常 | Redis 连接失败 | 高 |
| 磁盘不足 | 磁盘使用率 > 80% | 中 |
| Beat主节点切换 | RedBeat 主节点切换 | 高 |
| 熔断器开启 | 任意熔断器进入 Open 状态 | 高 |
| 容器频繁重启 | 容器5分钟内重启 >3次 | 高 |
| 任务停滞 | 任务超过1小时未更新 | 中 |
| 健康检查失败 | 容器健康检查连续失败 | 高 |
5.4.2 告警通知方式
1. 数据库通知: 存入 Notification 表
2. 邮件通知: 发送到管理员邮箱（需配置）
3. Webhook通知: 发送到钉钉/企业微信（可选）
---
6. 容量规划
6.1 业务量预估
业务规模:
- 平均日订单量: 50-150个
- 高峰日订单量: 200-300个
- 不同关键词数: 10-20个/天
- 每个关键词关联订单: 5-15个
处理能力:
- 单个订单处理时间: 15-20分钟（优化后）
- 日订单总处理时间: 2-4小时（优化后）
- 高峰期处理时间: 6-8小时（优化后）
6.2 资源需求
服务器配置（推荐）:
- CPU: 8核
- 内存: 16GB
- 磁盘: 100GB SSD
- 带宽: 10Mbps+

进程资源分配:
- Gunicorn Web: 2-4 个 worker 进程
- Celery Worker: 5-10 个并发进程（根据队列配置）
- Celery Beat 节点1: 1 个进程
- Celery Beat 节点2: 1 个进程
- Flower: 1 个进程
- 健康监控脚本: 1 个进程

内存预估:
- Gunicorn Web: 500MB × 2 = 1GB
- Celery Worker: 800MB × 5 = 4GB
- Celery Beat: 100MB × 2 = 200MB
- Redis: 2GB
- PostgreSQL: 2GB
- 操作系统及其他: 2GB
- 总计: 约 11GB
Worker 部署方案:
# Fast 队列（1个并发）
celery -A myproject worker -c 1-Q fast -n worker_fast@%h
# Slow 队列（2个并发）
celery -A myproject worker -c 13-Q slow -n worker_slow@%h
# ML 队列（3个并发）
celery -A myproject worker -c 3 -Q ml -n worker_ml@%h
# Browser 队列（3个并发）
celery -A myproject worker -c 3 -Q browser -n worker_browser@%h
# LLM 队列（2个并发）
celery -A myproject worker -c 2 -Q llm -n worker_llm@%h
# Normal 队列（2个并发）
celery -A myproject worker -c 2 -Q normal -n worker_normal@%h
# Maintenance 队列（1个并发）
celery -A myproject worker -c 1 -Q maintenance -n worker_maint@%h
# Beat 调度器（1个）
celery -A myproject beat -l info -S django_celery_beat.schedulers:DatabaseScheduler
总 Worker 数: 15个进程
---
7. 数据库优化
7.1 索引优化
新增索引:
-- ZhihuQuestion 表
CREATE INDEX idx_zhihu_keyword_created ON mvp_zhihuquestion(keyword, created_at DESC);
-- QuestionBank 表
CREATE INDEX idx_qb_keyword_cluster ON mvp_questionbank(keyword, cluster_id);
-- AIAnswer 表
CREATE INDEX idx_ai_keyword_qid ON mvp_aianswer(keyword, question_id);
CREATE INDEX idx_ai_date ON mvp_aianswer(answer_date DESC);
-- QuestionScore 表
CREATE INDEX idx_score_keyword_qid ON mvp_questionscore(keyword, question_id);
CREATE INDEX idx_score_date ON mvp_questionscore(answer_date DESC);
-- TaskLog 表
CREATE INDEX idx_tasklog_order ON mvp_tasklog(order_id);
CREATE INDEX idx_tasklog_status ON mvp_tasklog(status);
CREATE INDEX idx_tasklog_started ON mvp_tasklog(started_at DESC);
-- Mention_percentage 表（现有，优化）
CREATE INDEX idx_mention_brand_kw_date ON mvp_mention_percentage(brand_name, keyword_name, created_at DESC);
7.2 查询优化
批量查询示例:
# 使用 select_related 减少 SQL 查询
Order.objects.select_related('user').filter(status='completed')
# 使用 prefetch_related 关联查询
Order.objects.prefetch_related('notification_set')
# 使用 only() 只查询必要字段
Order.objects.only('id', 'keyword', 'brand', 'status', 'created_at')
# 使用 bulk_create 批量插入
QuestionBank.objects.bulk_create([...], batch_size=100)
# 使用 bulk_update 批量更新
Order.objects.bulk_update([...], fields=['status'], batch_size=100)
---
8. 安全和权限
8.1 数据安全
敏感数据保护:
- LLM API 密钥存储在环境变量
- 数据库密码存储在 Docker secrets
- Redis 密码（启用认证时）存储在环境变量
数据访问控制:
- 用户只能查看自己的订单
- 管理员可以查看所有订单和日志
- API 端点需要登录认证
8.2 任务安全
任务权限控制:
- 只有管理员可以手动触发任务
- 用户只能查看自己订单的任务状态
- 失败任务需要管理员权限才能重试
---
9. 部署检查清单
9.1 环境准备
- [ ] 安装 Python 3.9+
- [ ] 安装 PostgreSQL 15（系统服务）
- [ ] 安装 Redis 7（系统服务）
- [ ] 安装 Supervisor（进程管理）
- [ ] 安装 Nginx（反向代理，可选）
- [ ] 配置环境变量（/path/to/myproject/.env 或系统环境变量）
- [ ] 配置 LLM API 密钥
- [ ] 配置邮件服务（可选）
- [ ] 安装 Python 依赖：`pip install celery-redbeat pybreaker gunicorn supervisor`
9.2 数据库配置
- [ ] 创建 PostgreSQL 数据库和用户
- [ ] 配置 PostgreSQL 监听地址和端口
- [ ] 配置 Redis 监听地址和端口
- [ ] 验证数据库和 Redis 连接
9.3 数据库迁移
- [ ] 创建虚拟环境: `python -m venv venv`
- [ ] 激活虚拟环境: `source venv/bin/activate`
- [ ] 安装依赖: `pip install -r requirements.txt`
- [ ] 执行数据库迁移: `python manage.py migrate`
- [ ] 扩展 TaskLog 表（新增进度字段）
- [ ] 创建数据库索引
- [ ] 创建超级用户: `python manage.py createsuperuser`
- [ ] 收集静态文件: `python manage.py collectstatic`
9.4 Supervisor 配置
- [ ] 创建 Supervisor 配置文件: `/etc/supervisor/conf.d/myproject.conf`
- [ ] 配置 Gunicorn Web 服务
- [ ] 配置 Celery Worker 服务
- [ ] 配置 Celery Beat 节点1
- [ ] 配置 Celery Beat 节点2
- [ ] 配置 Flower 监控服务
- [ ] 配置健康监控脚本（可选）
- [ ] 重新加载配置: `sudo supervisorctl reread && sudo supervisorctl update`
9.5 服务启动
- [ ] 启动 PostgreSQL: `sudo systemctl start postgresql`
- [ ] 启动 Redis: `sudo systemctl start redis`
- [ ] 启动所有 Supervisor 服务: `sudo supervisorctl start all`
- [ ] 验证服务状态: `sudo supervisorctl status`
9.6 监控验证
- [ ] 访问 Flower 界面: http://server-ip:5555
- [ ] 验证 Worker 状态（在线/离线）
- [ ] 验证任务队列长度
- [ ] 验证任务执行情况
- [ ] 验证 Beat 调度状态: `redis-cli -p 6380 GET redbeat:master`
- [ ] 验证 Supervisor 进程状态: `sudo supervisorctl status`
- [ ] 测试熔断器：手动触发API故障，观察状态变化
- [ ] 测试断点续传：中断任务后重启，验证进度恢复
- [ ] 测试告警通知
9.7 高可用验证
- [ ] 停止主 Beat 节点，验证备节点是否接管: `sudo supervisorctl stop celery-beat-1`
- [ ] 重启主 Beat 节点，验证是否自动加入备节点列表: `sudo supervisorctl start celery-beat-1`
- [ ] 停止 Worker，验证自动重启: `sudo supervisorctl stop celery-worker && sleep 10 && sudo supervisorctl status celery-worker`
- [ ] 查看健康检查日志: `tail -f /var/log/health-monitor/monitor.log`
- [ ] 验证 Redis 锁机制: `redis-cli -p 6380 KEYS redbeat:*`
9.8 Nginx 配置（可选）
- [ ] 配置 Nginx 反向代理 Gunicorn
- [ ] 配置 SSL 证书（Let's Encrypt）
- [ ] 配置静态文件服务
- [ ] 测试访问: `https://your-domain.com`
---
10. 风险和应对
10.1 技术风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| Celery Beat 单点故障 | 定时任务失效 | 使用 celery-redBeat 实现分布式调度 |
| Worker 进程崩溃 | 任务中断 | Docker 健康检查 + 自动重启 |
| Playwright 无头模式不稳定 | 任务失败 | 熔断器保护 + 断点续传 |
| LLM API 限流 | 任务延迟 | 熔断器保护 + 指数退避重试 |
| 数据库连接池耗尽 | 服务不可用 | 熔断器保护 + 增加连接池大小 |
| Redis 内存溢出 | 缓存失效 | 设置内存淘汰策略，定期清理 |
| 任务处理中断 | 数据重复 | 断点续传机制 + 进度记录 |
10.2 业务风险
| 风险 | 影响 | 应对措施 |
|------|------|----------|
| 高峰期订单积压 | 用户体验下降 | 增加并发数，优化任务调度 |
| 数据丢失 | 业务中断 | 定期备份数据库和 Redis |
| 成本超预算 | 运营成本增加 | 监控 API 调用次数，设置告警阈值 |
| 任务长时间失败 | 用户投诉 | 断点续传 + 自动恢复机制 |
10.3 新增风险应对详情
10.3.1 Celery Beat 故障恢复
故障场景:
- Beat 节点崩溃
- Redis 连接中断
- 调度锁失效

应对流程:
1. 备节点自动接管（秒级切换）
2. 恢复节点后自动检测并加入备节点列表
3. 监控告警发送到管理员

验证方式:
```bash
# 停止主节点
docker stop celery-beat-1
# 观察备节点是否接管
redis-cli -h redis -p 6380 GET redbeat:master
```
10.3.2 任务中断恢复
故障场景:
- Worker 进程 OOM 崩溃
- 机器重启
- 网络中断

应对流程:
1. Docker 自动重启 Worker
2. 任务重试时读取进度检查点
3. 从断点继续处理

验证方式:
```python
# 模拟中断
kill -9 $(pgrep -f celery)
# 观察任务是否从断点恢复
curl http://localhost:8000/api/task/123/progress/
```
10.3.3 熔断器恢复策略
故障场景:
- LLM API 连续限流
- 知乎反爬封锁
- 数据库连接异常

应对流程:
1. 熔断器开启，阻止后续请求
2. 超时后进入半开状态
3. 探测性调用，成功则关闭熔断器
4. 失败则重新进入开启状态

验证方式:
```python
# 模拟API故障
# 修改代码抛出异常
# 观察熔断器状态变化
docker logs celery | grep "熔断器"
```
---
11. 后续优化方向
11.1 性能优化
- 使用异步客户端（aiohttp）替代同步客户端
- 实现浏览器连接池，复用浏览器实例
- 使用 GPU 加速 SentenceTransformer
- 实现智能调度，根据 Worker 负载动态分配任务
11.2 功能优化
- 实现更细粒度的权限控制
- 增强断点续传：支持跨节点恢复（Redis 共享进度）
- 熔断器动态配置：支持运行时调整参数
11.3 运维优化
- 实现多服务器负载均衡
- 实现数据库主从复制
- 实现 Redis 集群
- 实现自动化部署流水线（CI/CD）
- 实现 Nginx 负载均衡和反向代理
---
附录：术语表
| 术语 | 说明 |
|------|------|
| Celery | 分布式任务队列框架 |
| Celery Beat | Celery 的定时调度器 |
| Flower | Celery 的实时监控工具 |
| Chord | Celery 的任务组合模式（并行执行后回调） |
| Chain | Celery 的任务链模式（串行执行） |
| Redis | 内存数据库，用作消息代理和缓存 |
| PostgreSQL | 关系型数据库，存储业务数据 |
| Playwright | 浏览器自动化工具 |
| SentenceTransformer | 文本向量化模型 |
| LLM | 大语言模型（Large Language Model） |
| RedBeat | Celery 的分布式 Beat 调度器 |
| 熔断器 | Circuit Breaker，故障隔离机制 |
| 断路续传 | 任务中断后从断点恢复的机制 |
| 健康检查 | 定期检查服务状态的机制 |
| 自愈 | 服务故障后自动恢复的机制 |
---
附录B：新增技术组件说明
B.1 celery-redBeat
作用：实现 Celery Beat 的分布式高可用调度
安装：
```bash
pip install celery-redbeat
```
核心特性：
- 支持 Celery Beat 的多节点部署
- 通过 Redis 存储调度状态和锁
- 自动故障转移，无单点故障
- 支持动态调度任务
配置文件：
```python
# settings.py
CELERY_BEAT_SCHEDULER = 'redbeat.RedBeatScheduler'
CELERY_REDBEAT_REDIS_URL = 'redis://redis:6380/1'
CELERY_REDBEAT_LOCK_TIMEOUT = 30
```
B.2 pybreaker
作用：实现熔断器模式，防止级联故障
安装：
```bash
pip install pybreaker
```
核心特性：
- 支持三种状态：Closed、Open、Half-Open
- 可配置失败阈值和恢复超时
- 支持事件监听和监控
- 提供装饰器简化使用
配置文件：
```python
import pybreaker

llm_circuit_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=60,
    name='llm_api'
)
```
B.3 Supervisor 进程管理
作用：守护进程管理和自动重启
核心特性：
- 进程守护和自动重启
- 支持多个进程管理
- 日志文件管理
- 进程状态监控
配置文件：
```ini
[program:celery-worker]
command=/path/to/venv/bin/celery -A myproject worker -l info --hostname=worker@%%h
directory=/path/to/myproject
user=www-data
numprocs=5
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
exitcodes=0,1
environment=CELERY_BROKER_URL="redis://localhost:6380/0"
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker.err
```

常用命令:
```bash
# 查看所有进程状态
sudo supervisorctl status

# 启动服务
sudo supervisorctl start celery-worker

# 停止服务
sudo supervisorctl stop celery-worker

# 重启服务
sudo supervisorctl restart celery-worker

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update

# 查看日志
sudo supervisorctl tail celery-worker
sudo supervisorctl tail -f celery-worker stderr
```
B.4 断点续传实现
作用：任务中断后从断点继续处理
核心特性：
- 进度记录到数据库（TaskLog）
- 支持 JSON 格式的检查点存储
- 自动检测断点并恢复
- 支持手动重试和自动恢复
数据模型：
```python
class TaskLog(models.Model):
    progress_checkpoint = models.JSONField(blank=True, null=True)
    processed_items = models.IntegerField(default=0)
    total_items = models.IntegerField(default=0)
    last_checkpoint_time = models.DateTimeField(blank=True, null=True)
```
检查点数据结构：
```json
{
  "stage": "collect_ai_answers",
  "keyword": "蓝牙耳机",
  "completed_questions": ["qid_001", "qid_002"],
  "current_question": "qid_003",
  "question_count": 200
}
```
---
附录C：故障恢复流程图
C.1 Celery Beat 故障恢复
```
主节点崩溃
    ↓
Supervisor 检测到进程退出
    ↓
Supervisor 自动重启主节点
    ↓
备节点检测到锁超时
    ↓
备节点竞争获取锁
    ↓
备节点成为新的主节点
    ↓
主节点重启后作为备节点运行
    ↓
自动加入备节点列表
```
C.2 任务断点续传
```
任务执行中（处理第100/200个问题）
    ↓
Worker 进程崩溃
    ↓
Supervisor 检测到进程退出
    ↓
Supervisor 自动重启 Worker
    ↓
Celery 任务重试机制触发
    ↓
读取 TaskLog.progress_checkpoint
    ↓
发现已完成 1-99 个问题
    ↓
从第 100 个问题继续处理
    ↓
任务完成，清理检查点
```
C.3 熔断器状态切换
```
正常状态（Closed）
    ↓
连续调用失败3次
    ↓
熔断器开启（Open）
    ↓
快速失败，拒绝所有请求
    ↓
等待60秒（reset_timeout）
    ↓
进入半开状态（Half-Open）
    ↓
允许1个探测请求
    ↓
请求成功 → 关闭熔断器（Closed）
请求失败 → 重新开启（Open）
```
---
附录D：完整 Supervisor 配置示例
文件路径: /etc/supervisor/conf.d/myproject.conf
```ini
[group:myproject]
programs=gunicorn,celery-worker,celery-beat-1,celery-beat-2,flower,health-monitor

[program:gunicorn]
command=/path/to/venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 2 --threads 4 myproject.wsgi:application
directory=/path/to/myproject
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
environment=PATH="/path/to/venv/bin",DJANGO_SETTINGS_MODULE="myproject.settings"
stdout_logfile=/var/log/gunicorn/myproject.log
stderr_logfile=/var/log/gunicorn/myproject.err

[program:celery-worker]
command=/path/to/venv/bin/celery -A myproject worker -l info --hostname=worker@%%h
directory=/path/to/myproject
user=www-data
numprocs=5
process_name=%(program_name)s_%(process_num)02d
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
exitcodes=0,1
environment=PATH="/path/to/venv/bin",CELERY_BROKER_URL="redis://localhost:6380/0",CELERY_RESULT_BACKEND="redis://localhost:6380/1"
stdout_logfile=/var/log/celery/worker.log
stderr_logfile=/var/log/celery/worker.err

[program:celery-beat-1]
command=/path/to/venv/bin/celery -A myproject beat -l info -S redbeat.RedBeatScheduler --hostname=beat1@%%h
directory=/path/to/myproject
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
environment=PATH="/path/to/venv/bin",CELERY_BROKER_URL="redis://localhost:6380/0",CELERY_REDBEAT_REDIS_URL="redis://localhost:6380/1"
stdout_logfile=/var/log/celery/beat1.log
stderr_logfile=/var/log/celery/beat1.err

[program:celery-beat-2]
command=/path/to/venv/bin/celery -A myproject beat -l info -S redbeat.RedBeatScheduler --hostname=beat2@%%h
directory=/path/to/myproject
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
environment=PATH="/path/to/venv/bin",CELERY_BROKER_URL="redis://localhost:6380/0",CELERY_REDBEAT_REDIS_URL="redis://localhost:6380/1"
stdout_logfile=/var/log/celery/beat2.log
stderr_logfile=/var/log/celery/beat2.err

[program:flower]
command=/path/to/venv/bin/flower -A myproject --port=5555 --broker=redis://localhost:6380/0
directory=/path/to/myproject
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
environment=PATH="/path/to/venv/bin"
stdout_logfile=/var/log/flower/flower.log
stderr_logfile=/var/log/flower/flower.err

[program:health-monitor]
command=/bin/bash /path/to/scripts/health_monitor.sh
user=www-data
numprocs=1
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
stdout_logfile=/var/log/health-monitor/monitor.log
stderr_logfile=/var/log/health-monitor/monitor.err
```
---
文档版本: v2.1
编写日期: 2025-01-25
适用版本: AI可见度评估系统 v2.1
