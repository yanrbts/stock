import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

def get_falling_stocks(threshold=0):
    """
    获取当前下跌的A股股票
    :param threshold: 跌幅阈值(默认0表示所有下跌股票，设为-5可获取跌幅超5%的股票)
    :return: DataFrame(代码,名称,最新价,涨跌幅,成交量,成交额)
    """
    try:
        # 尝试多个数据源获取
        data_sources = [
            lambda: ak.stock_zh_a_spot_em().rename(columns={
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'pct_chg',
                '成交量': 'volume',
                '成交额': 'amount'
            }),
            lambda: ak.stock_zh_a_spot().rename(columns={
                '代码': 'symbol',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'pct_chg',
                '成交量': 'volume',
                '成交额': 'amount'
            })
        ]
        
        for source in data_sources:
            try:
                df = source()
                if not df.empty and 'pct_chg' in df.columns:
                    # 筛选下跌股票并按跌幅排序
                    falling = df[df['pct_chg'] <= threshold][[
                        'symbol', 'name', 'price', 'pct_chg', 'volume', 'amount'
                    ]]
                    return falling.sort_values('pct_chg').reset_index(drop=True)
            except Exception as e:
                print(f"数据源尝试失败: {str(e)}")
                continue
        
        raise Exception("所有数据源获取失败")
        
    except Exception as e:
        print(f"获取下跌股票失败: {str(e)}")
        return pd.DataFrame()

def analyze_falling_stocks(df):
    """分析下跌股票数据"""
    if df.empty:
        print("无下跌股票数据可分析")
        return
    
    # 计算统计指标
    analysis = {
        "股票总数": len(df),
        "平均跌幅": f"{df['pct_chg'].mean():.2f}%",
        "最大跌幅": f"{df['pct_chg'].min():.2f}%",
        "跌幅中位数": f"{df['pct_chg'].median():.2f}%",
        "跌停股票数": len(df[df['pct_chg'] <= -9.9])
    }
    
    # 按行业统计（需额外获取行业数据）
    try:
        industry_df = ak.stock_board_industry_name_em()
        merged = pd.merge(df, industry_df, left_on='symbol', right_on='股票代码', how='left')
        industry_analysis = merged['行业'].value_counts().head(5)
        analysis["跌幅最大前5行业"] = industry_analysis.to_dict()
    except:
        pass
    
    return analysis

def visualize_falling_stocks(df):
    """可视化下跌股票分布"""
    plt.figure(figsize=(12, 6))
    
    # 跌幅分布直方图
    plt.subplot(1, 2, 1)
    plt.hist(df['pct_chg'], bins=20, color='lightcoral', edgecolor='black')
    plt.title('股票跌幅分布')
    plt.xlabel('跌幅(%)')
    plt.ylabel('股票数量')
    plt.axvline(x=df['pct_chg'].mean(), color='red', linestyle='--')
    
    # 成交量TOP10
    plt.subplot(1, 2, 2)
    top10 = df.nsmallest(10, 'pct_chg')
    plt.barh(top10['name'], -top10['pct_chg'], color='indianred')
    plt.title('跌幅最大10只股票')
    plt.xlabel('跌幅(%)')
    plt.tight_layout()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    plt.savefig(f'falling_stocks_analysis_{timestamp}.png')
    plt.show()

if __name__ == "__main__":
    # 获取所有下跌股票
    falling_stocks = get_falling_stocks()
    
    if not falling_stocks.empty:
        print(f"\n=== 实时下跌股票 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
        print(f"下跌股票总数: {len(falling_stocks)}")
        print(falling_stocks.head(10).to_markdown(index=False))
        
        # 数据分析
        analysis = analyze_falling_stocks(falling_stocks)
        print("\n=== 数据分析 ===")
        for k, v in analysis.items():
            print(f"{k}: {v}")
        
        # 可视化
        visualize_falling_stocks(falling_stocks)
        
        # 保存数据
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"falling_stocks_{timestamp}.csv"
        falling_stocks.to_csv(filename, index=False, encoding='utf_8_sig')
        print(f"\n数据已保存到: {filename}")
    else:
        print("未获取到下跌股票数据")