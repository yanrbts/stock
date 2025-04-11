import akshare as ak
import pandas as pd
import time
from datetime import datetime, timedelta

def analyze_stock_trend(symbol="600519"):
    """
    分析指定股票的涨跌趋势
    参数：
        symbol: 股票代码（如 "600519" 为贵州茅台）
    返回：
        dict: 包含实时和历史趋势的分析结果
    """
    # 添加市场前缀
    full_symbol = f"sh{symbol}" if symbol.startswith(('6', '9')) else f"sz{symbol}"
    
    result = {
        "symbol": full_symbol,
        "name": None,
        "real_time_trend": None,
        "historical_trend": None,
        "pct_chg": None,
        "details": {}
    }

    # 1. 获取实时数据
    try:
        print(f"获取 {full_symbol} 的实时数据...")
        df_spot = ak.stock_zh_a_spot_em()
        stock_data = df_spot[df_spot['代码'] == symbol]
        
        if not stock_data.empty:
            stock_row = stock_data.iloc[0]
            result["name"] = stock_row['名称']
            result["pct_chg"] = stock_row['涨跌幅']
            result["details"]["price"] = stock_row['最新价']
            result["details"]["volume"] = stock_row['成交量']
            
            # 判断实时趋势
            if result["pct_chg"] > 0:
                result["real_time_trend"] = "上涨"
            elif result["pct_chg"] < 0:
                result["real_time_trend"] = "下跌"
            else:
                result["real_time_trend"] = "持平"
            print(f"实时数据获取成功: {result['name']} 当前涨跌幅 {result['pct_chg']}%")
        else:
            print(f"未找到 {full_symbol} 的实时数据")
    except Exception as e:
        print(f"实时数据获取失败: {e}")

    # 2. 获取历史数据（最近 20 天）
    try:
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        print(f"获取 {full_symbol} 的历史数据 ({start_date} 至 {end_date})...")
        
        df_hist = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"  # 前复权
        )
        
        if not df_hist.empty:
            # 计算最近 20 天收盘价变化趋势
            df_hist['pct_chg'] = df_hist['收盘'].pct_change() * 100  # 日涨跌幅
            last_close = df_hist['收盘'].iloc[-1]
            first_close = df_hist['收盘'].iloc[0]
            total_change = (last_close - first_close) / first_close * 100
            
            # 判断历史趋势
            if total_change > 0:
                result["historical_trend"] = "上涨"
            elif total_change < 0:
                result["historical_trend"] = "下跌"
            else:
                result["historical_trend"] = "持平"
            
            result["details"]["historical_data"] = df_hist[['日期', '收盘', 'pct_chg']].to_dict(orient="records")
            result["details"]["total_change"] = total_change
            print(f"历史数据获取成功: 最近 20 天总变化 {total_change:.2f}%")
        else:
            print(f"未找到 {full_symbol} 的历史数据")
    except Exception as e:
        print(f"历史数据获取失败: {e}")

    return result

def print_trend_analysis(result):
    """打印分析结果"""
    print("\n=== 股票趋势分析 ===")
    print(f"股票代码: {result['symbol']}")
    print(f"股票名称: {result['name']}")
    print(f"实时趋势: {result['real_time_trend']} (涨跌幅: {result['pct_chg']:.2f}%)")
    print(f"历史趋势 (最近 20 天): {result['historical_trend']}")
    print("\n详细信息:")
    if "price" in result["details"]:
        print(f"最新价: {result['details']['price']}")
        print(f"成交量: {result['details']['volume']}")
    if "total_change" in result["details"]:
        print(f"最近 20 天总变化: {result['details']['total_change']:.2f}%")
    if "historical_data" in result["details"]:
        print("最近 20 天收盘价及日涨跌幅:")
        for day in result["details"]["historical_data"]:
            print(f"日期: {day['日期']}, 收盘价: {day['收盘']}, 日涨跌幅: {day['pct_chg']:.2f}%")

def main():
    # 指定股票代码，例如贵州茅台
    stock_code = "601688"
    analysis_result = analyze_stock_trend(stock_code)
    print_trend_analysis(analysis_result)

if __name__ == "__main__":
    main()