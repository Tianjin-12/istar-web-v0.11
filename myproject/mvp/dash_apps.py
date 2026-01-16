# mvp/dash_apps.py
from django_plotly_dash import DjangoDash
from dash.dependencies import Output, Input, State
import dash_bootstrap_components as dbc
import os
import json
import subprocess
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np 
import requests
from datetime import timedelta,datetime
from django.urls import reverse
# 创建DjangoDash实例，名称必须与模板中的name属性匹配
app = DjangoDash('DashboardApp', external_stylesheets=[dbc.themes.BOOTSTRAP,"https://use.fontawesome.com/releases/v5.15.4/css/all.css",
                     "/static/css/style.css"],
                 suppress_callback_exceptions=True,
                 serve_locally=True,
                 meta_tags=[{"name": "viewport", "content": "width=device-width"}])
# --- 1. 多语言配置 ---
TRANSLATIONS = {
    'zh': {
        'nav_dash': '仪表盘', 'nav_rank': '行业榜单',
        'nav_wiki': 'AI 知识库', 'nav_setting': '系统设置',
        'login': '登录', 'welcome': '管理员', 'guest': '游客访问',
        # 搜索区
        'lbl_brand': '监测对象', 'ph_brand': '品牌名称 (如: Nike)',
        'lbl_kw': '核心关键词', 'ph_kw': '关键词 (如: 蓝牙耳机)',
        'btn_start': '开始分析',
        # KPI & 图表
        'kpi_vis': '核心品牌提及概率(推荐性任务)', 'kpi_sent': '链接提及概率',
        'kpi_rev': '品牌提及概率（随意性任务）', 'chart_trend': '流量来源趋势分析',
        'chart_rank': '竞品可见度排行 ', 'chart_pie': 'AI 平台推荐份额',
        'download': '导出分析报告', 'lang_label': 'EN'
    },
    'en': {
        'nav_dash': 'Dashboard', 'nav_rank': 'Rankings',
        'nav_wiki': 'Wiki', 'nav_setting': 'Settings',
        'login': 'Login', 'welcome': 'Admin', 'guest': 'Guest Mode',
        # Search Section
        'lbl_brand': 'Target Brand', 'ph_brand': 'e.g. Nike',
        'lbl_kw': 'Keywords', 'ph_kw': 'e.g. Wireless Earbuds',
        'btn_start': 'Analyze',
        # KPI & Charts
        'kpi_vis': 'Core Brand Mention percentage(recommend task)', 'kpi_sent': 'Link Mention percentage',
        'kpi_rev': 'Brand Mention percentage(random task)', 'chart_trend': 'Traffic Source Trends',
        'chart_rank': 'Visibility Ranking', 'chart_pie': 'AI Rec. Share',
        'download': 'Export Report', 'lang_label': '中'
    }
}
def fetch_backend_data(brand_name=None, keyword_name=None):
    # API端点URL
    base_url = os.environ.get("https://istar-geo.com",'http://localhost:8000')
    api_url = f"{base_url}/api/dashboard-data/"
    # 构建查询参数
    params = {}
    if brand_name:
        params['brand_name'] = brand_name
    if keyword_name:
        params['keyword'] = keyword_name
    params['days'] = 30  # 默认获取30天的数据
    
    try:
        # 发送GET请求到API
        response = requests.get(api_url, params=params, timeout=100)
        
        # 检查响应状态
        if response.status_code == 200:
            # 解析JSON响应
            data = response.json()
            
            if data.get('status') == 'success':
                # 获取API数据
                api_data = data.get('data', [])
                
                if not api_data:
                    # 如果没有数据，返回特殊标记
                    return {"no_data": True, "brand_name": brand_name, "keyword_name": keyword_name}
                
                # 将API数据转换为DataFrame
                df = pd.DataFrame(api_data)
                
                print(type(df))
                # 转换为网页需要的数据格式
                return df
            elif data.get('status') == 'no_data':
                # API返回没有数据的标记
                return {"no_data": True, "brand_name": data.get('brand_name', brand_name), "keyword_name": data.get('keyword_name', keyword_name)}
            else:
                # API返回错误
                print(f"API返回错误: {data.get('error', '未知错误')}")
                return {"no_data": True, "brand_name": brand_name, "keyword_name": keyword_name}
        else:
            # HTTP错误
            print(f"HTTP错误 {response.status_code}: {response.text}")
            return {"no_data": True, "brand_name": brand_name, "keyword_name": keyword_name}
            
    except requests.exceptions.RequestException as e:
        # 网络请求异常
        print(f"网络请求异常: {str(e)}")
        return {"no_data": True, "brand_name": brand_name, "keyword_name": keyword_name}
    except Exception as e:
        # 其他异常
        print(f"处理数据时发生异常: {str(e)}")
        return {"no_data": True, "brand_name": brand_name, "keyword_name": keyword_name}


def _convert_to_web_format(df,brand_name):
    # 处理趋势图数据
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _get_default_data()
    trend_data = {
        "Date": [],
        "Brand": [],
        "Link": []
    }
    focus_df = df[df["brand_name"] == brand_name]
    # 按日期分组并计算平均值
    
    focus_df["created_at"] = pd.to_datetime(focus_df["created_at"])
    df["created_at"] = pd.to_datetime(df["created_at"])
        # 获取最近的日期
    latest_date = focus_df["created_at"].max()    
        # 筛选出最近日期的数据
    latest_data = focus_df[focus_df["created_at"] == latest_date]   
        # 计算最近一天的平均值
    latest_r_brand_amount = latest_data['r_brand_amount'].mean()
    latest_nr_brand_amount = latest_data['nr_brand_amount'].mean()
    latest_link_amount = latest_data['link_amount'].mean()
    grouped = focus_df.groupby("created_at").agg({
            'r_brand_amount': 'mean',
            'link_amount': 'mean'
        }).reset_index()
        
        # 按日期排序
    grouped = grouped.sort_values("created_at")
        
        # 将日期转换为字符串格式
    trend_data["Date"] = grouped["created_at"].dt.strftime('%Y-%m-%d').tolist()
    trend_data["Brand"] = grouped['r_brand_amount'].tolist()
    trend_data["Link"] = grouped['link_amount'].tolist()
   
    # 处理排行榜数据
    ranking_data = pd.DataFrame(columns=['Brand', 'Score', 'Rank'])
    if 'brand_name' in df.columns and 'r_brand_amount' in df.columns and 'link_amount' in df.columns:
        # 按品牌分组，计算brand_amount和link_amount的平均值
        brand_stats = df.groupby('brand_name').agg({
            'r_brand_amount': 'mean',
            'link_amount': 'mean'
        }).reset_index()
        
        # 计算总分（brand_amount + link_amount）
        brand_stats['total_score'] = brand_stats['r_brand_amount'] + brand_stats['link_amount']
        
        # 按总分降序排列
        brand_stats = brand_stats.sort_values('total_score', ascending=False).reset_index(drop=True)
        
        # 添加排名列（从1开始）
        brand_stats['rank'] = range(1, len(brand_stats) + 1)
        
        # 重命名列以匹配期望的输出格式
        ranking_data = brand_stats.rename(columns={
            'brand_name': 'Brand',
            'total_score': 'Score',
            'rank': 'Rank'
        })
        
        # 选择需要的列
        ranking_data = ranking_data[['Brand', 'Score', 'Rank']]
    # 处理饼图数据
    pie_labels = brand_stats['brand_name'].tolist()
    pie_values = brand_stats['total_score'].tolist()
    return trend_data, ranking_data, pie_labels, pie_values,latest_r_brand_amount,latest_link_amount,latest_nr_brand_amount


def _get_default_data():
    # 生成默认日期范围
    dates = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(29, -1, -1)]
    
    # 默认趋势数据
    trend_data = {
        "Date": dates,
        "Brand": [0] * 30,
        "Link": [0] * 30
    }
    
    # 默认排行榜数据
    rank_data = pd.DataFrame({
        'Brand': ['暂无数据'],
        'Score': [0],
        'Rank': [1]
    })
    
    # 默认饼图数据
    BrandsP = ['暂无数据']
    values = [100]
    
    latest_r_brand_amount = 0
    latest_nr_brand_amount = 0
    latest_link_amount = 0
    return trend_data, rank_data, BrandsP, values,latest_r_brand_amount,latest_link_amount,latest_nr_brand_amount
# --- 2. 布局设计 ---
app.layout =html.Div([
    dcc.Location(id="refreshment",refresh=False),
    dcc.Store(id='lang-store', data='zh'),
    dcc.Store(id='user-store', data={'authenticated': False, 'username': None, 'email': None}),
    dcc.Store(id='login-state', data=False),  # 存储是否登录

    # === A. 顶部导航栏 (已升级品牌展示) ===
    dbc.Navbar(
        dbc.Container([
            dbc.Row([
                # 1. Logo
                dbc.Col(
                    html.Img(src="/assets/logo.png", className="navbar-logo"),
                    width="auto"
                ),
                # 2. 品牌文字区
                dbc.Col([
                    html.H4(
                        "Istar GEO Evaluator",
                        className="mb-0 fw-bold",
                        style={
                            "color": "#344767",
                            "fontSize": "1.25rem",
                            "lineHeight": "1.2"
                        }
                    ),
                    html.Small(
                        "基于 RAG 技术的品牌 AI 可见度与声量监测平台",
                        className="text-muted",
                        style={"fontSize": "0.75rem"}
                    )
                ], className="ps-2 d-flex flex-column justify-content-center"),

                # 3. 菜单链接
                dbc.Col(
                    dbc.Nav([
                        dbc.NavItem(dbc.NavLink(
                            id="nav-dash",
                            active=True,
                            className="nav-link-custom"
                        )),
                        dbc.NavItem(dbc.NavLink(
                            id="nav-rank",
                            className="nav-link-custom"
                        )),
                        dbc.NavItem(dbc.NavLink(
                            id="nav-wiki",
                            className="nav-link-custom"
                        )),
                        dbc.NavItem(dbc.NavLink(
                            id="nav-setting",
                            className="nav-link-custom"
                        )),
                    ], className="ms-5 d-none d-lg-flex"),
                    width=True
                ),
            ], align="center", className="flex-grow-1"),

            # 右侧：语言 + 登录
    dbc.Row([
        dbc.Col(
            dbc.Switch(
                id="lang-switch", value=False, className="me-3"
            ),
            width="auto"
        ),
        dbc.Col(
            html.Div(id="auth-button-container"),
            width="auto"
        )
    ], align="center", className="g-0")
    ], fluid=True),className=
    "navbar-glass sticky-top mb-4"
    ),
    # === C. 主要内容区域 ===
    dbc.Container([

        # --- 搜索控制台 ---
        dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    # 监测对象
                    dbc.Col([
                        html.Label(
                            id="lbl-search-brand",
                            className="small fw-bold text-secondary mb-1"
                        ),
                        dbc.Input(
                            id="input-search-brand",
                            className="form-control-premium"
                        )
                    ], width=12, md=4),

                    # 核心关键词
                    dbc.Col([
                        html.Label(
                            id="lbl-search-kw",
                            className="small fw-bold text-secondary mb-1"
                        ),
                        dbc.Input(
                            id="input-search-kw",
                            className="form-control-premium"
                        )
                    ], width=12, md=4),

                    # 按钮 (底部对齐)
                    dbc.Col([
                        html.Label(" ", className="d-block mb-1"),
                        dbc.Button(
                            id="btn-analyze",
                            className="w-100 fw-bold shadow-sm mb-2",
                            color="dark",
                            n_clicks=0
                        ),
                        dbc.Button(
                            id="btn-download",
                            className="w-100 fw-bold shadow-sm",
                            color="primary",
                            n_clicks=0
                        )
                    ], width=12, md=4)
                ], className="g-3 align-items-end")
            ], className="p-4")
        ], className="premium-card mb-5 border-0 shadow-sm"),

        # 添加下载组件
        dcc.Download(id="download-dataframe-csv"),

        dcc.Loading(
            id="loading",
            type="cube",
            color="#cb0c9f",
            children=[
                # 1. 三个大卡片 KPI
                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardBody([
                            html.Div(
                                id="label-kpi-1",
                                className="card-label mb-2"
                            ),
                            html.Div([
                                html.Span(
                                    id="val-1",
                                    className="metric-value"
                                ),
                                html.Span(id="bad-1")
                            ])
                        ])
                    ], className="premium-card h-100 delay-1"),
                        width=12, lg=4, className="mb-4"),

                    dbc.Col(dbc.Card([
                        dbc.CardBody([
                            html.Div(
                                id="label-kpi-2",
                                className="card-label mb-2"
                            ),
                            html.Div([
                                html.Span(
                                    id="val-2",
                                    className="metric-value"
                                ),
                                html.Span(id="bad-2")
                            ])
                        ])
                    ], className="premium-card h-100 delay-2"),
                        width=12, lg=4, className="mb-4"),

                    dbc.Col(dbc.Card([
                        dbc.CardBody([
                            html.Div(
                                id="label-kpi-3",
                                className="card-label mb-2"
                            ),
                            html.Div([
                                html.Span(
                                    id="val-3",
                                    className="metric-value"
                                ),
                                html.Span(id="bad-3")
                            ])
                        ])
                    ], className="premium-card h-100 delay-3"),
                        width=12, lg=4, className="mb-4"),
                ]),

                # 2. 图表区
                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardHeader(
                            id="title-trend",
                            className="bg-transparent border-0 fw-bold pt-4 ps-4"
                        ),
                        dbc.CardBody(
                            dcc.Graph(
                                id='chart-trend',
                                config={'displayModeBar': False},
                                style={"height": "320px"}
                            )
                        )
                    ], className="premium-card h-100"), width=12, lg=8, className="mb-4"),

                    dbc.Col(dbc.Card([
                        dbc.CardHeader(
                            id="title-pie",
                            className="bg-transparent border-0 fw-bold pt-4 ps-4"
                        ),
                        dbc.CardBody(
                            dcc.Graph(
                                id='chart-pie',
                                config={'displayModeBar': False},
                                style={"height": "320px"}
                            )
                        )
                    ], className="premium-card h-100"), width=12, lg=4, className="mb-4")
                ]),

                # 3. 排行榜
                dbc.Row([
                    dbc.Col(dbc.Card([
                        dbc.CardHeader(
                            id="title-rank",
                            className="bg-transparent border-0 fw-bold pt-4 ps-4"
                        ),
                        dbc.CardBody(id='rank-container', className="p-4")
                    ], className="premium-card"), width=12)
                ])
            ]
        )
    ], fluid=True, className="px-lg-5 pb-5"),

    # 全局定时器 (自动刷新)
    dcc.Interval(id="interval-trigger", interval=120 * 1000, n_intervals=0),
    dcc.Interval(id="auth-check-interval", interval=5 * 1000, n_intervals=0),
    # 用户信息模态框
dbc.Modal(
    [
        dbc.ModalHeader(dbc.ModalTitle("用户信息")),
        dbc.ModalBody([
            html.Div([
                html.P([
                    html.Strong("用户名: "),
                    html.Span(id="modal-username")
                ]),
                html.P([
                    html.Strong("邮箱: "),
                    html.Span(id="modal-email")
                ])
            ])
        ]),
        dbc.ModalFooter([
            dbc.Button("退出登录", id="logout-button", color="danger", className="me-2"),
            dbc.Button("关闭", id="close-user-modal", className="ms-auto")
        ])
    ],
    id="user-modal",
    is_open=False,
    centered=True,
    size="sm"
),
# 隐藏的 DataTable 防止 Import unused 报错
html.Div(dash_table.DataTable(id='hidden'), style={'display': 'none'}),
# 用于接收退出登录JavaScript的隐藏div
html.Div(id='logout-redirect', style={'display': 'none'})
])
#交互
@app.callback(
    [Output('nav-dash', 'children'), Output('nav-rank', 'children'),
     Output('nav-wiki', 'children'), Output('nav-setting', 'children'),
     Output('lbl-search-brand', 'children'),
     Output('input-search-brand', 'placeholder'),
     Output('lbl-search-kw', 'children'),
     Output('input-search-kw', 'placeholder'),
     Output('btn-analyze', 'children'),
     Output('btn-download', 'children'),
     Output('label-kpi-1', 'children'), Output('label-kpi-2', 'children'),
     Output('label-kpi-3', 'children'),
     Output('title-trend', 'children'), Output('title-pie', 'children'),
     Output('title-rank', 'children'),
     Output('lang-store', 'data')],
    [Input('lang-switch', 'value')]
)
def update_language(is_en):
    lang = 'en' if is_en else 'zh'
    t = TRANSLATIONS[lang]
    return (
        t['nav_dash'], t['nav_rank'], t['nav_wiki'], t['nav_setting'],
        t['lbl_brand'], t['ph_brand'], t['lbl_kw'], t['ph_kw'], t['btn_start'],t['download'],
        t['kpi_vis'], t['kpi_sent'], t['kpi_rev'],
        t['chart_trend'], t['chart_pie'], t['chart_rank'],
        lang
    )

# C. 数据图表渲染 (监听自动刷新 OR 手动点击分析)
@app.callback(
    [Output('val-1', 'children'), Output('bad-1', 'children'),
     Output('val-2', 'children'), Output('bad-2', 'children'),
     Output('val-3', 'children'), Output('bad-3', 'children'),
     Output('chart-trend', 'figure'), Output('chart-pie', 'figure'),
     Output('rank-container', 'children')],
    [Input('interval-trigger', 'n_intervals'),
     Input('btn-analyze', 'n_clicks')],
    [State('input-search-brand', 'value'),State('input-search-kw', 'value')]
)
def update_metrics(n_interval, n_click, search_brand,search_keyword):
    # 检查是否是点击了分析按钮
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 获取数据
    data = fetch_backend_data(brand_name=search_brand, keyword_name=search_keyword)
    
    # 检查是否没有数据
    if isinstance(data, dict) and data.get("no_data"):
        brand_name = data.get("brand_name", "")
        keyword_name = data.get("keyword_name", "")
        
        # 返回一个特殊的UI，提示用户创建订单
        no_data_message = dbc.Card([
            dbc.CardBody([
                html.H4("暂无数据", className="card-title"),
                html.P(f"数据库中没有找到关于 '{brand_name}' 和 '{keyword_name}' 的数据。", className="card-text"),
                html.P("请先创建订单以开始数据分析。", className="card-text"),
                dbc.Button("创建订单", 
                          color="primary", 
                          href=f"/api/redirect-to-create-order/?brand_name={brand_name}&keyword_name={keyword_name}",
                          className="mt-3",
                          external_link=True),
                html.Div([
                    html.Small("提示：创建订单后系统将自动开始数据收集和分析", 
                             className="text-muted mt-2")
                ])
            ])
        ], className="mb-4")
        
        # 返回空数据和提示信息
        return "0%", "", "0%", "", "0%", "", go.Figure(), go.Figure(), no_data_message
    # 触发 fetch_data，传入搜索词 
    trend, rank, pie_l, pie_v ,latest_r_brand_amount,latest_link_amount,latest_nr_brand_amount = _convert_to_web_format(fetch_backend_data(brand_name=search_brand,keyword_name=search_keyword),search_brand)

    def badge(v):
        change = np.random.randint(-10, 20)
        if change > 0:
            color, icon = "#ecfdf5", "text-success ▲"
        else:
            color, icon = "#fef2f2", "text-danger ▼"

        return f"{v}%", html.Span(
            f"{icon} {abs(change)}%",
            className="trend-badge",
            style={"background": color}
        )

    # 1. 趋势图
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(
        x=trend["Date"], y=trend["Brand"], name="Brand Traffic",
        fill='tozeroy',
        line=dict(color="#d61616", width=3, shape='spline')
    ))
    fig1.add_trace(go.Scatter(
        x=trend["Date"], y=trend["Link"], name="Link Traffic",
        line=dict(color="#152FC2", width=3, shape='spline')
    ))
    fig1.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=10, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.1)
    )

    # 2. 饼图
    fig2 = go.Figure(data=[go.Pie(
        labels=pie_l, values=pie_v, hole=.7,
        textinfo='percent', textposition='outside',
        marker=dict(colors=px.colors.qualitative.Pastel)
    )])
    fig2.update_layout(
        showlegend=True,
        margin=dict(l=20, r=20, t=0, b=20),
        legend=dict(orientation="h")
    )

    # 3. 排行榜
    ranks = []
    for _, r in rank.iterrows():
        rk = r['Rank']
        cls = f"rank-{rk}" if rk <= 3 else "rank-other"

        # 如果是用户搜索的品牌(有输入)，加重显示
        extra_style = {}
        if rk == search_brand:
            extra_style = {"color": "#cb0c9f"}

        ranks.append(dbc.Row([
            dbc.Col(
                html.Div(f"{rk}", className=f"rank-circle {cls}"),
                width="auto"
            ),
            dbc.Col(
                html.Span(
                    r['Brand'],
                    className="fw-bold ms-3",
                    style=extra_style
                ),
                width=True
            ),
            dbc.Col(
                html.Span(f"{r['Score']}", className="fw-bold text-dark"),
                width="auto"
            )
        ], className="ranking-item align-items-center"))
    
    
    v1, b1 = badge(latest_r_brand_amount)
    v2, b2 = badge(latest_link_amount)
    v3, b3 = badge(latest_nr_brand_amount) 

    return v1, b1, v2, b2, v3, b3, fig1, fig2, ranks
    
@app.callback(
    [Output('kpi-mentions', 'children'),
     Output('kpi-links', 'children'),
     Output('kpi-top', 'children'),
     Output('kpi-ratio', 'children'),
     Output('trend-chart', 'figure'),
     Output('pie-chart', 'figure'),
     Output('data-table', 'data'),
     Output('data-table', 'columns')],
    [Input('submit-button', 'n_clicks')],
    [State('input-brand', 'value'),
     State('input-keyword', 'value'),
     State('platform-filter', 'value')],
)

# 添加 dcc.Download 组件到布局中，用于处理文件下载
@app.callback(
    Output("download-dataframe-csv", "data"),
    Input("btn-download", "n_clicks"),
    [State('input-search-brand', 'value'),
     State('input-search-kw', 'value')],
    prevent_initial_call=True,
)
def export_csv(n_clicks, search_brand, search_keyword):
    # 获取真实数据
    df = fetch_backend_data(brand_name=search_brand, keyword_name=search_keyword)
    
    # 检查返回的数据类型
    if isinstance(df, list) and len(df) > 0 and df[0] == 404:
        # 如果返回的是错误码
        df = pd.DataFrame({'Error': ['Data not found or API error']})
        #deflaut情况
    elif isinstance(df, tuple):
        df = pd.DataFrame({'Info': ['No data available for export']})
    elif df is None or df.empty:
        # 如果数据为空
        df = pd.DataFrame({'Info': ['No data available for export']})
    
    # 确保df是DataFrame类型
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame({'Info': ['Unexpected data format']})
    
    # 返回CSV数据以供下载
    return dcc.send_data_frame(df.to_csv, "dashboard_data.csv", index=False)

# 检查登录状态的回调函数
@app.callback(
    Output('user-store', 'data'),
    [Input('auth-check-interval', 'n_intervals'),
     Input('refreshment','pathname')]
)
def check_user_status(n_intervals, pathname):
    try:
        # 调用API检查登录状态
        url = 'http://localhost:8000/api/accounts/auth-check/'
        print(f"正在检查登录状态，URL: {url}")
        response = requests.get(url)
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"返回的数据: {data}")
            return data
    except Exception as e:
        print(f"检查登录状态时出错: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # 如果出错，返回未登录状态
    print("返回默认未登录状态")
    return {'authenticated': False, 'username': None, 'email': None}

# 根据登录状态显示不同的按钮
@app.callback(
    Output('auth-button-container', 'children'),
    [Input('user-store', 'data')]
)
def update_auth_button(user_data):
    if user_data and user_data.get('authenticated'):
        # 用户已登录，显示用户名按钮
        return html.A(
            dbc.Button(
                user_data.get('username'),
                color="dark",
                outline=True,
                className="rounded-pill fw-bold px-4 btn-sm",
                id="user-info-button"
            ),
            href="#",
            id="user-info-link",
            className="text-decoration-none",
            style={"display": "block"}  # 确保按钮可见
        )
    else:
        # 用户未登录，显示登录按钮，但仍然包含user-info-link ID
        return html.Div([
            html.A(
                dbc.Button(
                    "登录",
                    color="dark",
                    outline=True,
                    className="rounded-pill fw-bold px-4 btn-sm"
                ),
                href="/api/accounts/login/",
                target="_blank",
                className="text-decoration-none",
                id = "login-button"
            ),
            # 添加一个隐藏的user-info-link元素，确保ID存在
            html.Div(id="user-info-link", style={"display": "none"})
        ])
    
# 控制用户信息模态框的显示
@app.callback(
    [Output('user-modal', 'is_open'),
     Output('modal-username', 'children'),
     Output('modal-email', 'children')],
    [Input('user-info-link', 'n_clicks'),
     Input('close-user-modal', 'n_clicks'),
     Input('logout-button', 'n_clicks')],
    [State('user-store', 'data'),
     State('user-modal', 'is_open')]
)
def toggle_user_modal(user_info_clicks, close_clicks, logout_clicks, user_data, is_open):
    ctx = dash.callback_context
    if not ctx.triggered:
        return False, "", ""
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # 点击用户信息按钮，打开模态框
    if trigger_id == 'user-info-link' and user_info_clicks:
        if user_data and user_data.get('authenticated'):
            return True, user_data.get('username', ''), user_data.get('email', '')
        return False, "", ""
    
    # 点击关闭按钮，关闭模态框
    elif trigger_id == 'close-user-modal' and close_clicks:
        return False, "", ""
    
    # 点击退出登录按钮，关闭模态框并执行退出登录
    elif trigger_id == 'logout-button' and logout_clicks:
        # 这里我们只是关闭模态框，实际的退出登录逻辑将在下一个回调中处理
        return False, "", ""
    
    # 默认情况下，保持当前状态
    return is_open, dash.no_update, dash.no_update

