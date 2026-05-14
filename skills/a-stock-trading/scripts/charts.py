#!/usr/bin/env python3
"""
图表生成模块 - 为持仓分析、收益对比生成可视化图表
"""

import json
import os
import sys
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np

# === 中文字体配置 ===
CHINESE_FONTS = [
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/System/Library/Fonts/STHeiti Medium.ttc',
    '/Library/Fonts/Arial Unicode.ttf',
]

def _find_chinese_font():
    for fp in CHINESE_FONTS:
        if os.path.exists(fp):
            return fp
    for f in fm.findSystemFonts():
        try:
            prop = fm.FontProperties(fname=f)
            name = prop.get_name()
            if any(kw in name.lower() for kw in ['pingfang', 'heiti', 'noto', 'wqy', 'source han']):
                return f
        except:
            continue
    return None

FONT_PATH = _find_chinese_font()
if FONT_PATH:
    plt.rcParams['font.family'] = fm.FontProperties(fname=FONT_PATH).get_name()
    plt.rcParams['font.sans-serif'] = [fm.FontProperties(fname=FONT_PATH).get_name()]
else:
    plt.rcParams['font.sans-serif'] = ['Heiti TC', 'PingFang SC', 'STHeiti']
plt.rcParams['axes.unicode_minus'] = False

COLORS = {
    'up': '#E74C3C',
    'down': '#2ECC71',
    'flat': '#95A5A6',
    'bg': '#1A1A2E',
    'card': '#16213E',
    'text': '#FFFFFF',
    'text_dim': '#8899AA',
    'accent': '#F39C12',
    'grid': '#2C3E50',
}

def round_to(val, step):
    return round(val / step) * step


def _get_stock_data():
    """获取持仓数据 - 优先 efinance, 备胎 Sina

    Returns:
        (data_dict, data_date_str): 行情数据字典 和 数据日期
        数据日期为交易日期(非实时获取日期)，方便判断是否盘中
    """
    codes = ['603538', '603778', '300342', '000925', '300067', '600396', '000593']
    result = {}
    data_date = None

    # Method 1: efinance
    try:
        import efinance as ef
        df = ef.stock.get_realtime_quotes(codes)
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                code = str(row['股票代码']).zfill(6)
                result[code] = {
                    'name': row['股票名称'],
                    'price': float(row['最新价']),
                    'change_pct': float(row['涨跌幅']),
                    'high': float(row['最高']),
                    'low': float(row['最低']),
                    'open': float(row['今开']),
                    'volume': float(row.get('成交量', 0)),
                    'turnover_rate': float(row.get('换手率', 0)),
                    'pe': float(row.get('动态市盈率', 0) or 0) or 0,
                    'market_cap': float(row.get('总市值', 0) or 0) / 1e8
                    if float(row.get('总市值', 0) or 0) > 0 else 0,
                }
            if result:
                return result, datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        print(f"[WARN] efinance 失败, 切到 Sina: {e}", file=sys.stderr)

    # Method 2: Sina (意大利可用，含交易日期)
    try:
        import urllib.request
        sina_codes = []
        for c in codes:
            prefix = 'sh' if c.startswith('6') else 'sz'
            sina_codes.append(f'{prefix}{c}')
        url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
        req = urllib.request.Request(url, headers={'Referer': 'https://finance.sina.com.cn'})
        resp = urllib.request.urlopen(req, timeout=10)
        raw = resp.read().decode('gbk')

        for line in raw.strip().split(';'):
            if not line or '=' not in line:
                continue
            parts = line.split('=')[1].strip('"').split(',')
            if len(parts) < 30:
                continue
            code_key = line.split('=')[0].split('_')[-1]
            exchange = 'sh' if code_key.startswith('sh') else 'sz'
            code = code_key[2:].zfill(6)
            name = parts[0]
            price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[2]) if parts[2] else price
            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            high = float(parts[4]) if parts[4] else 0
            low = float(parts[5]) if parts[5] else 0
            volume = float(parts[8]) if parts[8] else 0

            # Sina 最后几个字段包含交易日期
            # ...idx, date, time, ...
            if not data_date and len(parts) >= 32:
                candidate_date = parts[30].strip()
                if candidate_date and '-' in candidate_date:
                    data_date = candidate_date

            result[code] = {
                'name': name,
                'price': price,
                'change_pct': round(change_pct, 2),
                'high': high,
                'low': low,
                'open': float(parts[1]) if parts[1] else 0,
                'volume': volume,
                'turnover_rate': 0,
                'pe': 0,
                'market_cap': 0,
            }

        if result:
            print(f"[INFO] Sina 获取 {len(result)} 只股票行情, 数据日期={data_date}", file=sys.stderr)
            return result, data_date or datetime.now().strftime('%Y-%m-%d')
    except Exception as e:
        print(f"[WARN] Sina 也失败了: {e}", file=sys.stderr)

    return None, None


def load_portfolio():
    path = os.path.expanduser('~/.openclaw/data/portfolio.json')
    if not os.path.exists(path):
        print(f"❌ 持仓文件不存在: {path}", file=sys.stderr)
        return None
    with open(path) as f:
        data = json.load(f)
    return data.get('positions', [])


def _prepare_portfolio_data():
    """准备持仓计算数据

    Returns:
        (items, total_cost, total_value, total_pnl, total_pnl_pct, data_label)
        data_label: 数据来源日期文本，如 '4月30日收盘' 或 '5月5日盘中'
    """
    positions = load_portfolio()
    if not positions:
        return None, None, None, None, None, ''

    stock_data, data_date = _get_stock_data()
    items = []
    total_cost = total_value = 0

    # 判断数据是盘中还是收盘
    today = datetime.now().strftime('%Y-%m-%d')
    if data_date == today:
        # 检查是否在交易时间
        now_h = datetime.now().hour + datetime.now().minute / 60
        # 北京时间 = Rome + 6, A股交易 9:30-15:00 CST
        beijing_h = now_h + 6
        if 9.5 <= beijing_h <= 15:
            data_label = f'{data_date} 盘中'
        else:
            data_label = f'{data_date} 收盘'
    elif data_date:
        data_label = f'{data_date} 收盘(最近交易日)'
    else:
        data_label = '最近交易日'

    for pos in positions:
        code = pos['code']
        cost = pos['cost']
        qty = pos['quantity']
        cost_total = cost * qty

        if stock_data and code in stock_data:
            sd = stock_data[code]
            cur_price = sd['price']
            change_pct = sd['change_pct']
            turnover = sd.get('turnover_rate', 0)
            pe = sd.get('pe', 0)
            mcap = sd.get('market_cap', 0)
        else:
            cur_price = cost
            change_pct = 0
            turnover = 0
            pe = 0
            mcap = 0

        cur_value = cur_price * qty
        pnl = cur_value - cost_total
        pnl_pct = (pnl / cost_total) * 100

        items.append({
            'name': pos['name'],
            'code': code,
            'cost': cost_total,
            'value': cur_value,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'price': cur_price,
            'change_pct': change_pct,
            'turnover': turnover,
            'pe': pe,
            'mcap': mcap,
        })
        total_cost += cost_total
        total_value += cur_value

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) * 100

    return items, total_cost, total_value, total_pnl, total_pnl_pct, data_label


def gen_portfolio_pnl_chart(output_path='/tmp/portfolio_pnl.png'):
    """持仓收益率与盈亏金额图"""
    items, total_cost, total_value, total_pnl, total_pnl_pct, data_label = _prepare_portfolio_data()
    if not items:
        return None

    names = [f"{i['name']}\n({i['code']})" for i in items]
    pnl_pcts = [i['pnl_pct'] for i in items]
    pnl_amounts = [i['pnl'] for i in items]
    bar_colors = [COLORS['up'] if p >= 0 else COLORS['down'] for p in pnl_pcts]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
    fig.patch.set_facecolor(COLORS['bg'])

    # === 左：收益率水平柱状图 ===
    ax1.set_facecolor(COLORS['card'])
    y_pos = range(len(names))
    bars = ax1.barh(y_pos, pnl_pcts, color=bar_colors, height=0.6, edgecolor='white', linewidth=0.5)
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(names, fontsize=11, color=COLORS['text'])
    ax1.set_xlabel('收益率 (%)', fontsize=12, color=COLORS['text_dim'])
    ax1.set_title('持仓收益率', fontsize=15, color=COLORS['text'], fontweight='bold', pad=15)

    max_pct = max(abs(p) for p in pnl_pcts)
    x_pad = max_pct * 0.15 + 2

    for i, (bar, pct, amt) in enumerate(zip(bars, pnl_pcts, pnl_amounts)):
        label = f"{pct:+.2f}%  (¥{amt:+,.0f})"
        if pct >= 0:
            ax1.text(bar.get_width() + x_pad*0.1, bar.get_y() + bar.get_height()/2,
                     label, ha='left', va='center', fontsize=10, color=COLORS['text'], fontweight='bold')
        else:
            ax1.text(bar.get_width() - x_pad*0.2, bar.get_y() + bar.get_height()/2,
                     label, ha='right', va='center', fontsize=10, color=COLORS['text'], fontweight='bold')

    ax1.axvline(x=0, color=COLORS['text_dim'], linewidth=0.8)
    margin = max_pct * 0.3 + 3
    ax1.set_xlim(min(pnl_pcts) - margin, max(pnl_pcts) + margin)
    ax1.tick_params(colors=COLORS['text_dim'])
    for spine in ['top', 'right']:
        ax1.spines[spine].set_visible(False)
    ax1.spines['left'].set_color(COLORS['grid'])
    ax1.spines['bottom'].set_color(COLORS['grid'])

    # === 右：盈亏占比饼图 ===
    ax2.set_facecolor(COLORS['bg'])
    abs_amts = [abs(a) for a in pnl_amounts]
    if sum(abs_amts) > 0:
        pie_colors = [COLORS['up'] if a >= 0 else COLORS['down'] for a in pnl_amounts]
        short_names = [i['name'] for i in items]
        wedges, texts, autotexts = ax2.pie(
            abs_amts, labels=short_names,
            autopct=lambda pct: f'{pct:.1f}%',
            colors=pie_colors, startangle=90,
            textprops={'color': COLORS['text'], 'fontsize': 9},
            pctdistance=0.75,
            wedgeprops={'edgecolor': COLORS['card'], 'linewidth': 1.5}
        )
        for at in autotexts:
            at.set_color('white')
            at.set_fontweight('bold')
    ax2.set_title('盈亏金额占比', fontsize=15, color=COLORS['text'], fontweight='bold', pad=15)

    fig.text(0.5, 0.92, f'组合总收益: ¥{total_pnl:+,.0f}  ({total_pnl_pct:+.2f}%)',
             ha='center', fontsize=14, color=COLORS['accent'], fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#2C3E50', edgecolor=COLORS['accent'], linewidth=1))

    fig.text(0.5, 0.02, f'数据: Sina 实时行情 | 数据日期: {data_label} | 瑞瑞',
             ha='center', fontsize=9, color=COLORS['text_dim'])

    plt.tight_layout(rect=[0, 0.04, 1, 0.90])
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"✅ 已保存: {output_path}", file=sys.stderr)
    return output_path


def gen_portfolio_summary(output_path='/tmp/portfolio_dashboard.png'):
    """持仓仪表盘 - 卡片风格"""
    items, total_cost, total_value, total_pnl, total_pnl_pct, data_label = _prepare_portfolio_data()
    if not items:
        return None

    fig = plt.figure(figsize=(18, 9))
    fig.patch.set_facecolor(COLORS['bg'])

    # 标题
    title_color = COLORS['up'] if total_pnl >= 0 else COLORS['down']
    fig.suptitle(f'持仓总览 | 成本 ¥{total_cost:,.0f} -> 市值 ¥{total_value:,.0f} | {"+" if total_pnl >= 0 else ""}{total_pnl:+,.0f} ({total_pnl_pct:+.2f}%)',
                 fontsize=16, color=title_color, fontweight='bold', y=0.96, ha='center',
                 bbox=dict(boxstyle='round,pad=0.4', facecolor=COLORS['card'], edgecolor=title_color, linewidth=1))

    n = len(items)
    for i, item in enumerate(items):
        pnl_color = COLORS['up'] if item['pnl'] >= 0 else COLORS['down']
        chg_color = COLORS['up'] if item['change_pct'] >= 0 else COLORS['down']

        ax = fig.add_axes([0.03 + (i % 4) * 0.235, 0.50 - (i // 4) * 0.42, 0.22, 0.38])
        ax.set_facecolor(COLORS['card'])
        ax.axis('off')

        # 名称
        ax.text(0.5, 0.90, f"{item['name']} ({item['code']})",
                ha='center', va='center', fontsize=12, color=COLORS['text'], fontweight='bold')

        # 现价
        ax.text(0.5, 0.73, f"¥{item['price']:.2f}",
                ha='center', va='center', fontsize=22, color=COLORS['text'], fontweight='bold')
        ax.text(0.5, 0.63, f"{item['change_pct']:+.2f}%",
                ha='center', va='center', fontsize=13, color=chg_color, fontweight='bold')

        # 详细信息
        info_lines = [
            (f"成本", f"¥{item['cost']:,.0f}"),
            (f"市值", f"¥{item['value']:,.0f}"),
            (f"盈亏", f"¥{item['pnl']:+,.0f} ({item['pnl_pct']:+.2f}%)"),
        ]
        if item.get('turnover'):
            info_lines.append((f"换手", f"{item['turnover']:.1f}%"))

        y = 0.52
        for label, val in info_lines:
            ax.text(0.12, y, label, fontsize=8, color=COLORS['text_dim'])
            pnl_flag = '盈亏' in label
            val_color = pnl_color if pnl_flag else COLORS['text']
            ax.text(0.88, y, val, fontsize=9, color=val_color, ha='right',
                    fontweight='bold' if pnl_flag else 'normal')
            y -= 0.08

        # 底部：成本/市值对比条
        max_v = max(item['cost'], item['value']) * 1.4
        if max_v > 0:
            ax.barh(0.10, item['cost'] / max_v, height=0.04, color='#34495E', left=0)
            ax.barh(0.10, item['value'] / max_v, height=0.04, color=pnl_color, alpha=0.7, left=0)

    fig.text(0.5, 0.01, f'数据: Sina 实时行情 | 数据日期: {data_label} | 瑞瑞',
             ha='center', fontsize=9, color=COLORS['text_dim'])

    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg'])
    plt.close()
    print(f"✅ 已保存: {output_path}", file=sys.stderr)
    return output_path


if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if action in ('all', 'portfolio', 'pnl'):
        gen_portfolio_pnl_chart()
    if action in ('all', 'portfolio', 'summary'):
        gen_portfolio_summary()
