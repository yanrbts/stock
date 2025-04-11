import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from log import CPrint
import os

# 定义导出的名称
__all__ = ["PredictionValidator"]

class PredictionValidator:
    def __init__(self, csv_file="best_stock.csv", forecast_days=5):
        self.csv_file = csv_file
        self.forecast_days = forecast_days  # 预测天数，默认 5 天
        self.log = CPrint()
        self.df = None
        self.load_data()

    def load_data(self):
        """加载 CSV 文件数据"""
        if not os.path.isfile(self.csv_file):
            self.log.error(f"{self.csv_file} 不存在，无法验证")
            return
        self.df = pd.read_csv(self.csv_file, encoding='utf-8')
        self.log.info(f"已加载 {self.csv_file}，共 {len(self.df)} 条记录")

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
            if stock_data.empty or stock_data["日期"].iloc[-1] < end_date_str:
                self.log.error(f"未获取到 {symbol} 在 {end_date_str} 的数据")
                return None
            return stock_data["收盘"].iloc[-1]
        except Exception as e:
            self.log.error(f"获取 {symbol} 数据失败: {e}")
            return None

    def validate_single_prediction(self, row, current_date):
        """验证单条预测的准确性"""
        predict_date = datetime.strptime(row["日期"], "%Y-%m-%d")
        target_date = predict_date + timedelta(days=self.forecast_days)
        
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
        
        # 输出每个预测的结果
        self.log.info("\n=== 预测验证结果 ===")
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
            print("\n")
        
        # 计算准确百分比
        total_predictions = len(results)
        accurate_predictions = sum(1 for res in results if res["准确性"])
        accuracy_percentage = (accurate_predictions / total_predictions) * 100
        
        self.log.info(f"总预测次数: {total_predictions}")
        self.log.info(f"准确预测次数: {accurate_predictions}")
        self.log.success(f"预测准确百分比: {accuracy_percentage:.2f}%")

if __name__ == "__main__":
    validator = PredictionValidator()
    validator.validate_all_predictions()