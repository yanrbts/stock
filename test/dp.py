import akshare as ak

index_df = ak.stock_zh_index_daily(symbol="sh000001")  # 上证指数
print(index_df)

index_trend = (index_df['close'].iloc[-1] - index_df['close'].iloc[-5]) / index_df['close'].iloc[-5]
if index_trend < -0.02:  # 大盘跌超 2%
    print("大盘下跌趋势，谨慎操作")