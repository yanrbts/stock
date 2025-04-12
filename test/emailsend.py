import smtplib
import time
from email.mime.text import MIMEText
import traceback

class QQSender:
    def __init__(self, email, auth_code):
        self.email = email
        self.auth_code = auth_code
        
    def send(self, to, subject, content, max_retries=3):
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = self.email
        msg['To'] = to
        msg['Subject'] = subject
        
        for i in range(max_retries):
            try:
                server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=25)
                server.login(self.email, self.auth_code)
                server.sendmail(self.email, to, msg.as_string())
                server.quit()  # 显式关闭连接
                print(f"邮件发送成功到 {to}")
                return True
            except (smtplib.SMTPException, OSError) as e:
                print(f"尝试 {i+1}/{max_retries} 失败: {e}")
                traceback.print_exc()  # 打印详细堆栈
                if i < max_retries - 1:
                    time.sleep(5)
            finally:
                if 'server' in locals():
                    try:
                        server.quit()  # 确保连接关闭
                    except:
                        pass
        print("所有重试均失败")
        return False

# 使用示例
if __name__ == "__main__":
    sender = QQSender("772166784@qq.com", "wdjvptwkfcpmbfie")
    sender.send("772166784@qq.com", "测试主题", "测试内容")