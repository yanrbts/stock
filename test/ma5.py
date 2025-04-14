import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def compute_macd(close_series, fast=12, slow=26, signal=9):
    """
    手动计算 MACD
    """
    ema_fast = close_series.ewm(span=fast, adjust=False).mean()
    ema_slow = close_series.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    macd_hist = (dif - dea) * 2
    return pd.DataFrame({
        'macd_fast': dif,
        'macd_slow': dea,
        'macd_diff': macd_hist
    })

def get_stock_data_with_macd(symbol="600519", days=60):
    """
    获取股票历史数据并计算 MACD
    """
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    
    print(f"获取 {symbol} 的历史数据 ({start_date} 至 {end_date})...")
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust="qfq"
    )
    if df.empty:
        print(f"未获取到 {symbol} 的数据")
        return df
    
    print(f"获取到 {len(df)} 条数据")
    
    if len(df) < 26:
        print("错误：数据不足 26 天，无法计算 MACD")
        return df
    
    # 清洗空值
    if df['收盘'].isnull().any():
        print("警告：收盘价中存在空值，正在填充...")
        df['收盘'] = df['收盘'].ffill().bfill()
    
    # 转换为数值类型
    df['收盘'] = pd.to_numeric(df['收盘'], errors='coerce')
    if df['收盘'].isnull().any():
        print("错误：收盘价转换为数值后仍存在空值")
        return df
    
    # 检查 inf 或 -inf
    if not np.all(np.isfinite(df['收盘'])):
        print("警告：收盘价中包含 inf 或 -inf，正在清理...")
        df['收盘'] = df['收盘'].replace([np.inf, -np.inf], np.nan).ffill().bfill()
    
    # 打印清洗后的数据
    print("清洗后的收盘价（前5行）:", df['收盘'].head().tolist())
    print("收盘价类型:", df['收盘'].dtype)
    print("收盘价空值数量:", df['收盘'].isnull().sum())
    
    # 计算 MACD
    try:
        macd = compute_macd(df['收盘'])
        df = pd.concat([df, macd], axis=1)
        print("MACD 计算成功，最后 5 行：")
        print(df[['日期', '收盘', 'macd_fast', 'macd_slow', 'macd_diff']].tail())
    except Exception as e:
        print(f"MACD 计算出错: {e}")
        return df
    
    return df

# 测试代码
if __name__ == "__main__":
    df = get_stock_data_with_macd(symbol="600590", days=60)
    print(df)