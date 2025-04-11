import akshare as ak
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

def get_historical_data(symbol, days=20):
    """增强版历史数据获取函数"""
    try:
        # 统一股票代码格式
        symbol = symbol.upper()
        if not symbol.endswith(('.SH', '.SZ')):
            symbol = f"{symbol[:6]}.SH" if symbol.startswith(('6', '9')) else f"{symbol[:6]}.SZ"
        
        # 尝试多个数据源
        sources = [
            lambda: ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="hfq"),
            lambda: ak.stock_zh_a_daily(symbol=symbol.replace('.', ''), adjust="hfq"),
            lambda: ak.stock_zh_a_hist_em(symbol=symbol, period="daily")
        ]
        
        for source in sources:
            try:
                df = source()
                if len(df) >= days:
                    # 计算技术指标
                    df['ma5'] = df['收盘'].rolling(5).mean()
                    df['volume_ma10'] = df['成交量'].rolling(10).mean()
                    df['rsi'] = ta.rsi(df['收盘'], length=14)
                    macd = ta.macd(df['收盘'])
                    df = pd.concat([df, macd], axis=1)
                    return df[-days:]  # 返回最近N天数据
            except Exception as e:
                continue
        
        raise Exception("所有数据源均失败")
    
    except Exception as e:
        print(f"获取 {symbol} 历史数据失败: {str(e)}")
        return pd.DataFrame()


def select_potential_stock():
    """修正版选股函数"""
    df = get_rising_stocks_cached()
    if df.empty:
        return None
    
    for _, row in df[df['pct_chg'] > 2].iterrows():
        symbol = row['symbol']
        
        # 检查股票代码格式
        if not symbol.endswith(('.SH', '.SZ')):
            symbol = f"{symbol[:6]}.SH" if symbol.startswith(('6', '9')) else f"{symbol[:6]}.SZ"
        
        hist_df = get_historical_data(symbol)
        
        # 调试输出
        print(f"\n{symbol} 数据检查:")
        print(f"是否为空: {hist_df.empty}")
        print(f"数据天数: {len(hist_df) if not hist_df.empty else 0}")
        if not hist_df.empty:
            print(f"日期范围: {hist_df.index[0]} 至 {hist_df.index[-1]}")
        
        if hist_df.empty or len(hist_df) < 20:
            print(f"跳过 {symbol}：数据不足")
            continue

        # 计算指标
        last_close = hist_df['收盘'].iloc[-1]
        ma5 = hist_df['ma5'].iloc[-1]
        avg_volume = hist_df['avg_volume'].iloc[-1]
        rsi = hist_df['rsi'].iloc[-1]
        macd_fast = hist_df['MACD_12_26_9'].iloc[-1]
        macd_slow = hist_df['MACDs_12_26_9'].iloc[-1]
        macd_diff = hist_df['MACDh_12_26_9'].iloc[-1]

        # 计算量比
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0

        # 评分规则
        score = 0  # 初始化评分变量为 0，用于综合评估股票的上涨潜力

        # 涨跌幅（pct_chg）：当前股票的涨跌幅，单位为百分比
        # 权重为 2，表示涨跌幅是核心指标，每 1% 涨跌幅贡献 2 分
        # 例如：涨跌幅 5% -> 5 * 2 = 10 分
        score += pct_chg * 2

        # 量比（volume_ratio）：当前成交量与近期平均成交量的比值，反映资金活跃度
        # 如果量比 > 1.5，表示成交量显著放大，可能有资金介入
        # 加分规则：基础 15 分，乘以量比（上限为 5），避免异常高量比过度影响
        # 例如：量比 2 -> 15 * 2 = 30 分；量比 6 -> 15 * 5 = 75 分
        if volume_ratio > 1.5:
            score += 15 * min(volume_ratio, 5)

        # 换手率（turnover）：当日成交量占流通股本的比例，单位为百分比
        # 如果换手率 > 1%，表示股票交易活跃，可能吸引市场关注
        # 加分规则：基础 10 分，乘以换手率/10（上限为 2），避免过高换手率（可能风险）过度加分
        # 例如：换手率 3% -> 10 * (3/10) = 3 分；换手率 25% -> 10 * 2 = 20 分
        if turnover > 1:
            score += 10 * min(turnover / 10, 2)

        # RSI（相对强弱指数）：衡量股票超买/超卖状态，范围 0-100
        # 如果 RSI 在 30-70 之间，表示动能适中，既不过热也不过冷，加 15 分
        # 避免超买（>70）或超卖（<30）的股票，前者可能回调，后者可能无上涨动力
        if 30 < rsi < 70:
            score += 15
        # 如果 RSI >= 70，表示超买，可能面临回调风险，减 10 分
        elif rsi >= 70:
            score -= 10

        # MACD（指数平滑异同移动平均线）：捕捉趋势和买卖信号
        # 条件：快线（macd_fast）> 慢线（macd_slow）且 DIF（macd_diff）> 0
        # 表示短期趋势强于长期趋势，且看涨信号明确，加 20 分（高权重反映趋势重要性）
        if macd_fast > macd_slow and macd_diff > 0:
            score += 20

        # 短期趋势：当前价格（price）与 5 日均线（ma5）的关系
        # 如果 price > ma5，表示短期趋势向上，股票处于上升通道，加 15 分
        if price > ma5:
            score += 15

        log.info(f"{symbol} {name} {score} 最大评分：{max_score}")
        # 更新最佳候选
        if score > max_score:
            max_score = score
            best_candidate = {
                'symbol': symbol,
                'name': name,
                'pct_chg': pct_chg,
                'volume': current_volume,
                'volume_ratio': volume_ratio,
                'turnover': turnover,
                'rsi': rsi,
                'macd_fast': macd_fast,
                'macd_slow': macd_slow,
                'ma5': ma5,
                'score': score
            }

    return best_candidate

def main():
    # 筛选潜在上涨股票
    candidate = select_potential_stock()

    if candidate:
        print("\n=== 推荐可能上涨的股票 ===")
        print(f"代码: {candidate['symbol']}")
        print(f"名称: {candidate['name']}")
        print(f"当前涨跌幅: {candidate['pct_chg']:.2f}%")
        print(f"当前成交量: {candidate['volume']}")
        print(f"量比: {candidate['volume_ratio']:.2f}")
        print(f"换手率: {candidate['turnover']:.2f}%")
        print(f"RSI: {candidate['rsi']:.2f}")
        print(f"MACD 快线: {candidate['macd_fast']:.2f}, 慢线: {candidate['macd_slow']:.2f}")
        print(f"5 日均线: {candidate['ma5']:.2f}")
        print(f"综合评分: {candidate['score']:.2f}")
    else:
        print("未找到符合条件的股票")

if __name__ == "__main__":
    main()