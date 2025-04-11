import akshare as ak
import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta

def get_stock_data_with_macd(symbol="600519", days=60):
    """
    获取股票历史数据并计算 MACD（适应 22 条数据限制）
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
    print(df)
    if df.empty:
        print(f"未获取到 {symbol} 的数据")
        return df
    
    print(f"获取到 {len(df)} 条数据")
    if len(df) < 26:
        print("错误：数据不足 20 天，无法计算调整后的 MACD")
        return df
    
    # 检查收盘价数据
    if df['收盘'].isnull().any():
        print("警告：收盘价中存在空值，将填充为前值")
        df['收盘'] = df['收盘'].fillna(method='ffill')
    
    # 计算调整后的 MACD
    try:
        # 使用 fast=12, slow=20, signal=9 适应 22 条数据
        macd = ta.macd(df['收盘'], fast=12, slow=26, signal=9)
        
        if macd is None or macd.empty:
            print("错误：MACD 计算失败，可能数据仍有问题")
            return df
        
        # print("MACD 列名:", macd.columns.tolist())
        # print("MACD 数据预览:\n", macd.tail())
        
        df = pd.concat([df, macd], axis=1)
        
        # 重命名列名
        df = df.rename(columns={
            'MACD_12_26_9': 'macd_fast',
            'MACDs_12_26_9': 'macd_slow',
            'MACDh_12_26_9': 'macd_diff'
        })
        
        # print("重命名后列名:", df.columns.tolist())
        
    except Exception as e:
        print(f"MACD 计算出错: {e}")
        return df
    
    return df

def main():
    stock_code = "601688"
    df = get_stock_data_with_macd(stock_code, days=60)
    
    required_cols = ['日期', '收盘', 'macd_fast', 'macd_slow', 'macd_diff']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        print(f"错误：缺少以下列: {missing_cols}")
    else:
        print("\n数据包含所有目标列，最后 5 行：")
        print(df[required_cols].tail())

if __name__ == "__main__":
    main()