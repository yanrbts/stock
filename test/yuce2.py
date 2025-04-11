import akshare as ak
import pandas as pd
import pandas_ta as ta
import requests,time
from datetime import datetime, timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm  # 进度条工具
from functools import lru_cache  # 缓存函数结果
from log import CPrint

log = CPrint()

# 设置请求头
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# 配置带重试的会话
session = requests.Session()
retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

# 自定义请求函数
def custom_get(url, **kwargs):
    return session.get(url, headers=headers, **kwargs)

# 覆盖 akshare 的默认请求
ak.requests_get = custom_get

# 缓存实时数据（避免重复请求）
@lru_cache(maxsize=1)
def get_rising_stocks_cached():
    """获取当前上涨的 A 股股票（缓存结果）"""
    try:
        log.info("尝试从东方财富获取实时数据...")
        df = ak.stock_zh_a_spot_em()
        log.success("成功获取实时数据")
        
        # 统一列名
        df = df.rename(columns={
            '涨跌幅': 'pct_chg',
            '代码': 'symbol',
            '名称': 'name',
            '成交量': 'volume',
            '最新价': 'price',
            '换手率': 'turnover'
        })
        return df[['symbol', 'name', 'pct_chg', 'volume', 'price', 'turnover']]
    except Exception as e:
        print(f"实时数据获取失败: {e}")
        return pd.DataFrame()
    

def get_all_stocks_daily(date=None):
    """获取全市场股票日线数据（优化版）"""
    from tqdm import tqdm  # 确保导入 tqdm 用于进度条
    
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    
    log.info(f"开始获取 {date} 的日线数据...")
    
    try:
        # 1. 获取股票列表（确保代码格式正确）
        stock_list = ak.stock_info_a_code_name()
        stock_list['pure_code'] = stock_list['code'].str.extract(r'(\d+)')[0]  # 提取纯数字代码
        
        all_data = []
        failed_symbols = []
        
        # 2. 添加进度条
        for _, row in tqdm(stock_list.head(5).iterrows(), total=5, desc="获取日线数据"):
            pure_code = row['pure_code']
            name = row['name']
            
            # 动态添加市场前缀：6 或 9 开头为上交所（sh），其他为深交所（sz）
            symbol = f"sh{pure_code}" if pure_code.startswith(('6', '9')) else f"sz{pure_code}"
            
            log.info(f"股票 {symbol}({name}) 获取...")
            try:
                # 3. 使用更稳定的接口
                df = ak.stock_zh_a_hist(
                    symbol=pure_code,  # 注意：接口仍使用纯数字代码，前缀在后续处理
                    period="daily",
                    start_date=date,
                    end_date=date,
                    adjust="qfq"  # 后复权
                )
                
                if not df.empty:
                    last_row = df.iloc[-1].to_dict()
                    last_row.update({
                        'symbol': symbol,  # 使用带前缀的 symbol
                        'name': name,
                        'trade_date': date
                    })
                    all_data.append(last_row)
                else:
                    log.warning(f"股票 {symbol}({name}) 获取数据是空的...")
                    failed_symbols.append(symbol)
                
                # 4. 更智能的请求间隔
                time.sleep(max(0.3, 0.5 * (1 + len(failed_symbols)/10)))  # 错误越多间隔越长
            
            except Exception as e:
                log.error(f"股票 {symbol}({name}) 获取失败: {str(e)[:100]}...")
                failed_symbols.append(symbol)
                continue
        
        # 5. 结果处理
        if all_data:
            result_df = pd.DataFrame(all_data)
            log.success(f"成功获取 {len(result_df)} 只股票数据，失败 {len(failed_symbols)} 只")
            return result_df
        else:
            log.error("未获取到任何数据")
            return pd.DataFrame()
            
    except Exception as e:
        log.error(f"全市场数据获取异常: {e}")
        return pd.DataFrame()

def get_historical_data(symbol="873726", days=10):
    """获取股票历史数据（带详细错误检查）"""
    try:
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        
        log.info(f"获取 {symbol} 历史数据: {start_date} 至 {end_date}")
        
        # 检查股票代码格式（确保包含市场后缀）
        # if not symbol.endswith(('.SH', '.SZ')):
        #     symbol = f"{symbol}.SH" if symbol.startswith(('6', '9')) else f"{symbol}.SZ"
        
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="hfq"  # 尝试前复权数据
        )
        
        if df.empty:
            log.error(f"空数据返回，尝试其他接口...")
            # 备用数据源
            df = ak.stock_zh_a_daily(symbol=symbol.replace('.', ''), start_date=start_date, end_date=end_date, adjust="hfq")
        
        log.info(f"获取到 {len(df)} 条数据，字段: {df.columns.tolist()}")
        
        if len(df) < days:
            log.warning(f"数据不足 {days} 天，实际获取 {len(df)} 天")
        
        # 休眠 1 秒，避免频繁请求
        time.sleep(2)
        return df
    
    except Exception as e:
        log.error(f"获取 {symbol} 历史数据失败: {str(e)}")
        return pd.DataFrame()

def select_potential_stock():
    """筛选一只可能上涨的股票"""
    # 获取实时上涨股票（使用缓存）
    df = get_all_stocks_daily()
    if df.empty:
        log.error("未获取到实时数据")
        return None

    # 初步筛选：涨跌幅 > 2%
    candidates = df[df['涨跌幅'] > 2].copy()
    if candidates.empty:
        log.warning("没有符合条件的上涨股票")
        return None

    log.info(f"初步筛选出 {len(candidates)} 只上涨股票")

    # 添加技术指标分析
    best_candidate = None
    max_score = -1

    print(f"{candidates}")

    for index, row in candidates.iterrows():
        symbol = row['symbol']
        name = row['name']
        pct_chg = row['涨跌幅']
        current_volume = row['成交量']
        price = row['收盘']
        turnover = row['换手率']

        # 获取历史数据
        hist_df = get_historical_data(symbol)
        if hist_df.empty:
            log.warning(f"{symbol} {name} 数据不足5天，跳过")
            continue
        
        print(hist_df)
        # 计算指标
        last_close = hist_df['close'].iloc[-1]
        ma5 = hist_df['ma5'].iloc[-1]
        avg_volume = hist_df['volume'].iloc[-1]
        # rsi = hist_df['rsi'].iloc[-1]
        # macd_fast = hist_df['MACD_12_26_9'].iloc[-1]
        # macd_slow = hist_df['MACDs_12_26_9'].iloc[-1]
        # macd_diff = hist_df['MACDh_12_26_9'].iloc[-1]

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
    # get_historical_data()
    main()

    # stock_zh_a_hist_df = ak.stock_zh_a_hist(
    #     symbol="600734",
    #     period="daily",
    #     start_date="20250401",
    #     end_date="20250410",
    #     adjust="qfq"
    # )
    # print(stock_zh_a_hist_df)