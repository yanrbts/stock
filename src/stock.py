import akshare as ak
import pandas as pd
import pandas_ta as ta
import signal,sys
from datetime import datetime, timedelta
from tqdm import tqdm
from threading import Thread
import os, csv, time
import schedule
from log import CPrint
from email_sender import QQSender
from validator import PredictionValidator

log = CPrint()

class Stock:
    """ 个股 """

    def __init__(self, symbol):
        self.symbol = symbol
        self.full_symbol = f"sh{self.symbol}" if self.symbol.startswith(('6', '9')) else f"sz{self.symbol}"
        self.df = None
        self.result = {
            "symbol": self.full_symbol,
            "name": None,
            "real_time_trend": None,
            "historical_trend": None,
            "pct_chg": None,
            "details": {}
        }
        self.score = 0
        self.index_trend = 0

        # 邮件发送相关
        self.email_sender = QQSender("772166784@qq.com", "wdjvptwkfcpmbfie")
        self.receiver_email = "772166784@qq.com"
    
    def get_stock_score(self):
        """ 按照指定规则对股票进行评分 """

        # 初始化评分变量为 0，用于综合评估股票的上涨潜力
        score = 0  
        details = self.result["details"]

        # 提取必要指标
        pct_chg = self.result["pct_chg"] or 0
        price = details.get("price", 0)
        volume = details.get("volume", 0)
        turnover = details.get("turnover", 0)
        avg_volume = details.get("avg_volume", 0)
        rsi = details.get("rsi", 0)
        macd_fast = details.get("macd_fast", 0)
        macd_slow = details.get("macd_slow", 0)
        macd_diff = details.get("macd_diff", 0)
        ma5 = details.get("ma5", 0)

        # 如果 rsi 是 Series，取最新值
        if isinstance(rsi, pd.Series):
            rsi = rsi.iloc[-1] if not rsi.empty else 0
        
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
        
        self.score = score

        return score
    
    def get_stock_data_with_macd(self):
        """ 获取股票历史数据并计算 MACD """

        if self.df.empty:
            log.error(f"未获取到 {self.symbol} 的数据")
            return False

        if len(self.df) < 26:
            log.error("数据不足 26 天，无法计算调整后的 MACD")
            return False
        
        # 检查收盘价数据
        if self.df['收盘'].isnull().any():
            log.warning("收盘价中存在空值，将填充为前值")
            self.df['收盘'] = self.df['收盘'].fillna(method='ffill')
        
        # 计算调整后的 MACD
        try:
            # 使用 fast=12, slow=20, signal=9 适应 22 条数据
            macd = ta.macd(self.df['收盘'], fast=12, slow=26, signal=9)
            
            if macd is None or macd.empty:
                return False
            
            self.df = pd.concat([self.df, macd], axis=1)
            
            # 重命名列名
            # self.df = self.df.rename(columns={
            #     'MACD_12_26_9': 'macd_fast',
            #     'MACDs_12_26_9': 'macd_slow',
            #     'MACDh_12_26_9': 'macd_diff'
            # })
            
        except Exception as e:
            log.error(f"MACD 计算出错: {e}")
            return False
        
        return True
    
    def analyze_stock_trend(self, stock_data):
        """
        分析指定股票的涨跌趋势并获取评分所需数据
        参数：
            symbol: 股票代码（如 "600519" 为贵州茅台）
        返回：
            dict: 包含趋势和评分所需数据的分析结果
        """

        # 获取实时数据
        try:
            # log.info(f"获取 {self.full_symbol} 的实时数据...")
            
            if not stock_data.empty:
                stock_row = stock_data.iloc[0]
                self.result["name"] = stock_row['名称']
                self.result["pct_chg"] = stock_row['涨跌幅']
                self.result["details"]["price"] = stock_row['最新价']
                self.result["details"]["volume"] = stock_row['成交量']
                self.result["details"]["turnover"] = stock_row['换手率']
                
                if self.result["pct_chg"] > 0:
                    self.result["real_time_trend"] = "上涨"
                elif self.result["pct_chg"] < 0:
                    self.result["real_time_trend"] = "下跌"
                else:
                    self.result["real_time_trend"] = "持平"
                # log.success(f"实时数据获取成功: {self.result['name']} 当前涨跌幅 {self.result['pct_chg']}%")
            else:
                log.error(f"未找到 {self.full_symbol} 的实时数据")
        except Exception as e:
            log.error(f"实时数据获取失败: {e}")
         
    def get_stock_hist(self, days=60):
        """获取历史数据（最近 26 天，计算技术指标）"""

        try:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            # log.info(f"获取 {self.full_symbol} 的历史数据 ({start_date} 至 {end_date})...")
            
            # 获取指定时间段的历史数据
            self.df = ak.stock_zh_a_hist(
                symbol=self.symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            if self.get_stock_data_with_macd() == False:
                log.error("MACD 计算失败，可能数据仍有问题")
                return False

            if not self.df.empty:
                # 计算趋势
                self.df['pct_chg'] = self.df['收盘'].pct_change() * 100
                last_close = self.df['收盘'].iloc[-1]
                first_close = self.df['收盘'].iloc[0]
                total_change = (last_close - first_close) / first_close * 100
                
                if total_change > 0:
                    self.result["historical_trend"] = "上涨"
                elif total_change < 0:
                    self.result["historical_trend"] = "下跌"
                else:
                    self.result["historical_trend"] = "持平"
                
                # 计算技术指标
                self.df['ma5'] = self.df['收盘'].rolling(window=5).mean()
                self.df['avg_volume'] = self.df['成交量'].rolling(window=10).mean()
                self.df['rsi'] = ta.rsi(self.df['收盘'], length=14)

                # macd = ta.macd(df_hist['收盘'], fast=12, slow=26, signal=9)
                # df_hist = pd.concat([df_hist, macd], axis=1)
                
                self.result["details"]["historical_data"] = self.df[['日期', '收盘', 'pct_chg']].to_dict(orient="records")
                self.result["details"]["total_change"] = total_change
                self.result["details"]["ma5"] = self.df['ma5'].iloc[-1]
                self.result["details"]["avg_volume"] = self.df['avg_volume'].iloc[-1]
                # 修复：存储整个 RSI Series
                self.result["details"]["rsi"] = self.df['rsi'] 

                self.result["details"]["macd_fast"] = self.df['MACD_12_26_9'].iloc[-1]
                self.result["details"]["macd_slow"] = self.df['MACDs_12_26_9'].iloc[-1]
                self.result["details"]["macd_diff"] = self.df['MACDh_12_26_9'].iloc[-1]
                
                # log.success(f"历史数据获取成功: 最近 26 天总变化 {total_change:.2f}%")
            else:
                log.error(f"未找到 {self.full_symbol} 的历史数据")
                return False

        except Exception as e:
            log.error(f"历史数据获取失败: {e}")
            return False

        return True

    def print_trend_analysis(self):
        """打印分析结果和评分"""
        print("\n")
        log.info("=== 股票趋势分析 ===")
        log.info(f"股票代码: {self.result['symbol']}")
        log.info(f"股票名称: {self.result['name']}")
        log.info(f"实时趋势: {self.result['real_time_trend']} (涨跌幅: {self.result['pct_chg']:.2f}%)")
        log.info(f"历史趋势 (最近 20 天): {self.result['historical_trend']}")
        
        print("\n")
        log.info("=== 详细信息 ===")
        if "price" in self.result["details"]:
            log.info(f"最新价: {self.result['details']['price']}")
            log.info(f"成交量: {self.result['details']['volume']}")
            log.info(f"换手率: {self.result['details']['turnover']:.2f}%")
        if "total_change" in self.result["details"]:
            log.info(f"最近 20 天总变化: {self.result['details']['total_change']:.2f}%")
        if "rsi" in self.result["details"]:
            rsi = self.result["details"].get("rsi", 0)
            if isinstance(rsi, pd.Series):
                rsi = rsi.iloc[-1] if not rsi.empty else 0
                log.info(f"RSI: {rsi:.2f}")
        if "macd_fast" in self.result["details"]:
            log.info(f"MACD 快线: {self.result['details']['macd_fast']:.2f}, 慢线: {self.result['details']['macd_slow']:.2f}")
        if "ma5" in self.result["details"]:
            log.info(f"5 日均线: {self.result['details']['ma5']:.2f}")

        print("\n")
        log.success(f"综合评分: {self.score:.2f}")

    def save_to_csv(self, filename="best_stock.csv"):
        """将最佳股票数据保存到 CSV 文件"""

        current_date = datetime.now().strftime("%Y-%m-%d")
        headers = ["日期", "股票代码", "股票名称", "评分", "最新价", "预测趋势", "RSI", "MACD快线", "MACD慢线", "5日均线"]
        
        # 如果 rsi 是 Series，取最新值
        rsi = self.result["details"].get("rsi", 0)
        if isinstance(rsi, pd.Series):
            rsi = rsi.iloc[-1] if not rsi.empty else 0
        
        data = {
            "日期": current_date,
            "股票代码": self.result["symbol"],
            "股票名称": self.result["name"],
            "评分": self.score,
            "最新价": self.result["details"].get("price", 0),
            "预测趋势": self.result["real_time_trend"],  # 当前趋势作为预测依据
            "RSI": rsi,
            "MACD快线": self.result["details"].get("macd_fast", 0),
            "MACD慢线": self.result["details"].get("macd_slow", 0),
            "5日均线": self.result["details"].get("ma5", 0)
        }

        file_exists = os.path.isfile(filename)
        with open(filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if not file_exists:
                writer.writeheader()  # 仅在文件不存在时写入表头
            writer.writerow(data) 
        log.success(f"最佳股票数据已保存到 {filename}")


class Market:
    """ 大盘 sh000001 或者 sz000001"""

    def __init__(self, symbol):
        self.df = None
        self.symbol = symbol
        self.index_trend = 0
    
    def get_stock_market(self):
        """ 获取大盘指数作为评估参考指标 """
        try:
            index_df = ak.stock_zh_index_daily(symbol=self.symbol)
            index_trend = (index_df['close'].iloc[-1] - index_df['close'].iloc[-5]) / index_df['close'].iloc[-5]
            self.index_trend = index_trend
        except Exception as e:
            log.error(f"获取大盘数据失败: {e}")

def stock_analysis():
    # 获取所有沪深京 A 股实时行情数据

    log.info("获取所有 A 股实时行情数据...")
    df_spot = ak.stock_zh_a_spot_em()
    
    if df_spot.empty:
        log.error("未获取到任何实时行情数据")
        return
    
    # 存储每只股票的实例和评分
    stock_scores = []
    
    # 遍历所有股票
    total_rows = df_spot.shape[0]
    for _, row in tqdm(df_spot.head(200).iterrows(), total=200, desc="数据处理", position=0, leave=True):
        symbol = row['代码']
        stk = Stock(symbol)
        
        # 获取实时数据
        stock_data = df_spot[df_spot['代码'] == symbol]
        stk.analyze_stock_trend(stock_data)
        
        # 获取历史数据和技术指标
        if stk.get_stock_hist(days=60) == False:
            continue
        
        # 计算评分
        score = stk.get_stock_score()
        stock_scores.append((stk, score))
    
        # log.info(f"股票 {stk.full_symbol} ({stk.result['name']}) 最近26天涨跌幅 {stk.result['details']['total_change']:.2f}% 评分: {score:.2f}")
    
    market = Market("sh000001")
    market.get_stock_market()

    # 找到评分最高的股票
    if stock_scores:
        best_stock, best_score = max(stock_scores, key=lambda x: x[1])
        log.info(f"评分最高的股票: {best_stock.full_symbol} ({best_stock.result['name']})，评分: {best_score:.2f}")
        best_stock.print_trend_analysis()
        
        # 大盘趋势
        if market.index_trend < -0.02:
            # 大盘跌超 2%
            log.warning("大盘下跌趋势，谨慎操作")

        # RSI 趋势
        if isinstance(best_stock.result["details"]["rsi"], pd.Series) and len(best_stock.result["details"]["rsi"]) >= 5:
            rsi_trend = best_stock.result["details"]["rsi"].iloc[-1] - best_stock.result["details"]["rsi"].iloc[-5]
            if rsi_trend > 0 and best_stock.result["details"]["rsi"].iloc[-1] < 70:
                log.info("RSI 上涨但未超买，买入信号增强")
        else:
            log.warning("RSI 数据无效或不足，无法计算趋势")
        
        # 评分阈值
        rsi_value = best_stock.result["details"]["rsi"].iloc[-1] \
                    if isinstance(best_stock.result["details"]["rsi"], pd.Series) \
                    else best_stock.result["details"]["rsi"]

        if best_score > 60 and 40 < best_stock.result["details"]["rsi"].iloc[-1] < 65:
            email_body = "=== 股票分析结果 ===\n\n"
            email_body += f"股票: {best_stock.full_symbol} 评分: {best_score:.2f} 股票名称: ({best_stock.result['name']})\n"
            subject = f"股票分析结果 - {datetime.now().strftime('%Y-%m-%d')}"
            best_stock.email_sender.send(best_stock.receiver_email, subject, email_body)

            log.success(f"{best_stock.full_symbol} 符合买入条件，评分: {best_score:.2f}")
        
        # 保存保存到 CSV 文件
        best_stock.save_to_csv()
    else:
        log.error("未找到任何有效股票评分")

def validate_all_predictions():
    ''' 验证所有预测结果 '''

    log.info("验证所有预测结果...")

    validator = PredictionValidator(
        csv_file="best_stock.csv",
        forecast_days=5,
        sender_email="772166784@qq.com",       
        sender_password="wdjvptwkfcpmbfie",
        receiver_email="772166784@qq.com"
    )

    validator.validate_all_predictions()
def run_service():
    """ 启动定时服务,每天14:00执行 main() """

    log.info("启动股票分析服务...")
    schedule.every().day.at("23:22").do(stock_analysis)
    log.info("分析任务,每天23:01执行")
    schedule.every().day.at("23:28").do(validate_all_predictions)
    log.info("验证任务,每天22:00执行")
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            log.success("服务收到终止信号，退出...")
            break
        except Exception as e:
            log.error(f"服务运行中出错: {e}")
            time.sleep(60)  # 出错后等待1分钟继续

def signal_handler(sig, frame):
    log.success(f"Received KeyboardInterrupt. Cleaning up...")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    run_service()
