import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import os
from email_sender import QQSender
from log import CPrint

# 定义导出的名称
__all__ = ["PredictionValidator"]

class PredictionValidator:
    def __init__(self, csv_file="best_stock.csv", forecast_days=5, \
                sender_email=None, sender_password=None, receiver_email=None):
        self.csv_file = csv_file
        self.forecast_days = forecast_days  # 预测天数，默认 5 天
        self.log = CPrint()
        self.df = None
        self.receiver_email = receiver_email
        # 初始化 QQSender
        if sender_email and sender_password and receiver_email:
            self.email_sender = QQSender(
                email=sender_email,
                auth_code=sender_password
            )
        else:
            self.email_sender = None
            self.log.warning("未提供邮箱配置，邮件发送功能不可用")

        self.load_data()

    def load_data(self):
        """加载 CSV 文件数据"""
        if not os.path.isfile(self.csv_file):
            self.log.error(f"{self.csv_file} 不存在，无法验证")
            return
        self.df = pd.read_csv(self.csv_file, encoding='utf-8')
        self.log.info(f"已加载 {self.csv_file}，共 {len(self.df)} 条记录")
    
    def get_trading_date(self, start_date, forecast_days):
        """
        计算从 start_date 开始，经过 forecast_days 个交易日后的日期（排除周六、周日）
        
        参数：
            start_date (datetime): 起始日期
            forecast_days (int): 要计算的交易日数
        
        返回：
            datetime: 调整后的目标日期
        """
        current_date = start_date
        trading_days_count = 0
        
        while trading_days_count < forecast_days:
            current_date += timedelta(days=1)
            # 周一=0, 周日=6，排除周六(5)和周日(6)
            if current_date.weekday() < 5:
                trading_days_count += 1
        
        return current_date

    def get_future_price(self, symbol, start_date, target_date):
        """获取目标日期的收盘价"""
        symbol_code = symbol[2:]  # 去掉 "sh" 或 "sz"
        start_date_str = start_date.strftime("%Y%m%d")
        end_date_str = target_date.strftime("%Y%m%d")
        
        try:
            stock_data = ak.stock_zh_a_hist(
                symbol=symbol_code,
                period="daily",
                start_date=start_date_str,
                end_date=end_date_str,
                adjust="qfq"
            )
            
            if stock_data.empty:
                self.log.error(f"未获取到 {symbol} 在 {start_date_str} 到 {end_date_str} 之间的数据")
                return None
            
            # 将日期列转换为 datetime.date 对象进行比较
            last_date = pd.to_datetime(stock_data["日期"]).iloc[-1].date()
            target_date = target_date.date()  # 转换为 date 对象
            
            if last_date < target_date:
                self.log.error(f"未获取到 {symbol} 在 {end_date_str} 的数据，最后可用日期是 {last_date}")
                return None

            return stock_data["收盘"].iloc[-1]
        except Exception as e:
            self.log.error(f"获取 {symbol} 数据失败: {e}")
            return None

    def validate_single_prediction(self, row, current_date):
        """验证单条预测的准确性"""
        predict_date = datetime.strptime(row["日期"], "%Y-%m-%d")
        # 使用独立方法计算调整后的 target_date
        target_date = self.get_trading_date(predict_date, self.forecast_days)
        
        # 检查是否到达验证日期
        if current_date < target_date:
            self.log.warning(f"{row['股票代码']} 预测日期 {predict_date.strftime('%Y-%m-%d')} 未到 {target_date.strftime('%Y-%m-%d')}，跳过验证")
            return None
        
        # 获取 5 天后的价格
        final_price = self.get_future_price(row["股票代码"], predict_date, target_date)
        if final_price is None:
            return None
        
        # 计算价格变化
        initial_price = row["最新价"]
        price_change = (final_price - initial_price) / initial_price * 100
        predicted_trend = row["预测趋势"]
        
        # 判断预测准确性
        if predicted_trend == "上涨":
            is_accurate = price_change > 0
        elif predicted_trend == "下跌":
            is_accurate = price_change < 0
        else:  # 持平
            is_accurate = abs(price_change) < 2  # ±2% 视为持平
        
        return {
            "股票代码": row["股票代码"],
            "股票名称": row["股票名称"],
            "预测日期": predict_date.strftime("%Y-%m-%d"),
            "初始价格": initial_price,
            "目标日期": target_date.strftime("%Y-%m-%d"),
            "实际价格": final_price,
            "价格变化": price_change,
            "预测趋势": predicted_trend,
            "准确性": is_accurate
        }

    def validate_all_predictions(self):
        """验证所有预测并计算准确百分比"""
        if self.df is None or self.df.empty:
            self.log.error("无数据可验证")
            return
        
        current_date = datetime.now()
        results = []
        
        for _, row in self.df.iterrows():
            result = self.validate_single_prediction(row, current_date)
            if result:
                results.append(result)
        
        if not results:
            self.log.error("没有可验证的预测结果")
            return
        
        # 格式化邮件正文
        email_body = "=== 股票预测验证结果 ===\n\n"
        for res in results:
            email_body += f"股票: {res['股票代码']} ({res['股票名称']})\n"
            email_body += f"预测日期: {res['预测日期']}\n"
            email_body += f"初始价格: {res['初始价格']:.2f}\n"
            email_body += f"目标日期: {res['目标日期']}\n"
            email_body += f"实际价格: {res['实际价格']:.2f}\n"
            email_body += f"价格变化: {res['价格变化']:.2f}%\n"
            email_body += f"预测趋势: {res['预测趋势']}\n"
            email_body += f"准确性: {'准确' if res['准确性'] else '错误'}\n\n"
        
        # 输出每个预测的结果
        self.log.info("=== 预测验证结果 ===")
        for res in results:
            self.log.info(f"股票: {res['股票代码']} ({res['股票名称']})")
            self.log.info(f"预测日期: {res['预测日期']}")
            self.log.info(f"初始价格: {res['初始价格']:.2f}")
            self.log.info(f"目标日期: {res['目标日期']}")
            self.log.info(f"实际价格: {res['实际价格']:.2f}")
            self.log.info(f"价格变化: {res['价格变化']:.2f}%")
            self.log.info(f"预测趋势: {res['预测趋势']}")
            if res["准确性"]:
                self.log.success("预测准确")
            else:
                self.log.error("预测错误")
        
        # 计算准确百分比
        total_predictions = len(results)
        accurate_predictions = sum(1 for res in results if res["准确性"])
        accuracy_percentage = (accurate_predictions / total_predictions) * 100

        email_body += f"总预测次数: {total_predictions}\n"
        email_body += f"准确预测次数: {accurate_predictions}\n"
        email_body += f"预测准确百分比: {accuracy_percentage:.2f}%\n"
        
        self.log.info(f"总预测次数: {total_predictions}")
        self.log.info(f"准确预测次数: {accurate_predictions}")
        self.log.success(f"预测准确百分比: {accuracy_percentage:.2f}%")

        # 发送邮件
        if self.email_sender:
            try:
                subject = f"股票预测验证结果 - {current_date.strftime('%Y-%m-%d')}"
                self.email_sender.send(self.receiver_email, subject, email_body)
            except Exception as e:
                self.log.error(f"发送邮件失败: {e}")
        else:
            self.log.warning("未配置邮件发送器，跳过发送邮件")

if __name__ == "__main__":
    # 替换为您的邮箱配置
    validator = PredictionValidator(
        csv_file="best_stock.csv",
        forecast_days=5,
        sender_email="772166784@qq.com",            # 替换为您的发送者邮箱
        sender_password="wdjvptwkfcpmbfie",         # 替换为您的应用专用密码
        receiver_email="772166784@qq.com"           # 替换为接收者邮箱
    )
    validator.validate_all_predictions()