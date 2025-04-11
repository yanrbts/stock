
import akshare as ak
import pandas as pd
import pandas_ta as ta  # 用于计算技术指标
import time
from datetime import datetime, timedelta

def analyze_stock_trend(symbol="600519"):
    """
    分析指定股票的涨跌趋势并获取评分所需数据
    参数：
        symbol: 股票代码（如 "600519" 为贵州茅台）
    返回：
        dict: 包含趋势和评分所需数据的分析结果
    """
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
            result["details"]["turnover"] = stock_row['换手率']
            
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

    # 2. 获取历史数据（最近 20 天，计算技术指标）
    try:
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        print(f"获取 {full_symbol} 的历史数据 ({start_date} 至 {end_date})...")
        
        df_hist = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if not df_hist.empty:
            # 计算趋势
            df_hist['pct_chg'] = df_hist['收盘'].pct_change() * 100
            last_close = df_hist['收盘'].iloc[-1]
            first_close = df_hist['收盘'].iloc[0]
            total_change = (last_close - first_close) / first_close * 100
            
            if total_change > 0:
                result["historical_trend"] = "上涨"
            elif total_change < 0:
                result["historical_trend"] = "下跌"
            else:
                result["historical_trend"] = "持平"
            
            # 计算技术指标
            df_hist['ma5'] = df_hist['收盘'].rolling(window=5).mean()
            df_hist['avg_volume'] = df_hist['成交量'].rolling(window=10).mean()
            df_hist['rsi'] = ta.rsi(df_hist['收盘'], length=14)
            macd = ta.macd(df_hist['收盘'], fast=12, slow=26, signal=9)
            df_hist = pd.concat([df_hist, macd], axis=1)
            
            result["details"]["historical_data"] = df_hist[['日期', '收盘', 'pct_chg']].to_dict(orient="records")
            result["details"]["total_change"] = total_change
            result["details"]["ma5"] = df_hist['ma5'].iloc[-1]
            result["details"]["avg_volume"] = df_hist['avg_volume'].iloc[-1]
            result["details"]["rsi"] = df_hist['rsi'].iloc[-1]
            result["details"]["macd_fast"] = df_hist['MACD_12_26_9'].iloc[-1]
            result["details"]["macd_slow"] = df_hist['MACDs_12_26_9'].iloc[-1]
            result["details"]["macd_diff"] = df_hist['MACDh_12_26_9'].iloc[-1]
            
            print(f"历史数据获取成功: 最近 20 天总变化 {total_change:.2f}%")
        else:
            print(f"未找到 {full_symbol} 的历史数据")
    except Exception as e:
        print(f"历史数据获取失败: {e}")

    return result

def score_stock(result):
    """按照指定规则对股票进行评分"""
    score = 0  # 初始化评分变量为 0，用于综合评估股票的上涨潜力
    details = result["details"]
    
    # 提取必要指标
    pct_chg = result["pct_chg"] or 0
    price = details.get("price", 0)
    volume = details.get("volume", 0)
    turnover = details.get("turnover", 0)
    avg_volume = details.get("avg_volume", 0)
    rsi = details.get("rsi", 0)
    macd_fast = details.get("macd_fast", 0)
    macd_slow = details.get("macd_slow", 0)
    macd_diff = details.get("macd_diff", 0)
    ma5 = details.get("ma5", 0)
    
    # 计算量比
    volume_ratio = volume / avg_volume if avg_volume > 0 else 0
    
    # 涨跌幅（pct_chg）：当前股票的涨跌幅，单位为百分比
    # 权重为 2，每 1% 涨跌幅贡献 2 分
    score += pct_chg * 2
    
    # 量比（volume_ratio）：当前成交量与近期平均成交量的比值，反映资金活跃度
    # 如果量比 > 1.5，表示成交量显著放大，可能有资金介入
    # 加分规则：基础 15 分，乘以量比（上限为 5）
    if volume_ratio > 1.5:
        score += 15 * min(volume_ratio, 5)
    
    # 换手率（turnover）：当日成交量占流通股本的比例，单位为百分比
    # 如果换手率 > 1%，表示股票交易活跃
    # 加分规则：基础 10 分，乘以换手率/10（上限为 2）
    if turnover > 1:
        score += 10 * min(turnover / 10, 2)
    
    # RSI（相对强弱指数）：衡量股票超买/超卖状态，范围 0-100
    # 如果 RSI 在 30-70 之间，表示动能适中，加 15 分
    if 30 < rsi < 70:
        score += 15
    # 如果 RSI >= 70，表示超买，可能回调，减 10 分
    elif rsi >= 70:
        score -= 10
    
    # MACD：捕捉趋势和买卖信号
    # 快线 > 慢线 且 DIF > 0，表示看涨信号，加 20 分
    if macd_fast > macd_slow and macd_diff > 0:
        score += 20
    
    # 短期趋势：当前价格与 5 日均线比较
    # 如果 price > ma5，表示短期趋势向上，加 15 分
    if price > ma5:
        score += 15
    
    return score

def print_trend_analysis(result, score):
    """打印分析结果和评分"""
    print("\n=== 股票趋势分析 ===")
    print(f"股票代码: {result['symbol']}")
    print(f"股票名称: {result['name']}")
    print(f"实时趋势: {result['real_time_trend']} (涨跌幅: {result['pct_chg']:.2f}%)")
    print(f"历史趋势 (最近 20 天): {result['historical_trend']}")
    print(f"综合评分: {score:.2f}")
    print("\n详细信息:")
    if "price" in result["details"]:
        print(f"最新价: {result['details']['price']}")
        print(f"成交量: {result['details']['volume']}")
        print(f"换手率: {result['details']['turnover']:.2f}%")
    if "total_change" in result["details"]:
        print(f"最近 20 天总变化: {result['details']['total_change']:.2f}%")
    if "rsi" in result["details"]:
        print(f"RSI: {result['details']['rsi']:.2f}")
    if "macd_fast" in result["details"]:
        print(f"MACD 快线: {result['details']['macd_fast']:.2f}, 慢线: {result['details']['macd_slow']:.2f}")
    if "ma5" in result["details"]:
        print(f"5 日均线: {result['details']['ma5']:.2f}")

def main():
    stock_code = "600519"  # 贵州茅台
    analysis_result = analyze_stock_trend(stock_code)
    if analysis_result["name"]:  # 确保获取到数据
        score = score_stock(analysis_result)
        print_trend_analysis(analysis_result, score)
    else:
        print("无法评分，未获取到股票数据")

if __name__ == "__main__":
    main()