import smtplib
import time
from email.mime.text import MIMEText
import traceback
import socket
from log import CPrint

class QQSender:
    def __init__(self, email, auth_code):
        self.email = email
        self.auth_code = auth_code
        self.log = CPrint()
        
    def send(self, to, subject, content, max_retries=3, timeout=30):
        """发送邮件，带重试和详细日志"""
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = self.email
        msg['To'] = to
        msg['Subject'] = subject
        
        for attempt in range(1, max_retries + 1):
            server = None
            try:
                # 设置 socket 全局超时
                socket.setdefaulttimeout(timeout)
                self.log.info(f"尝试 {attempt}/{max_retries}：连接到 smtp.qq.com:465")
                
                # 初始化 SMTP 连接
                server = smtplib.SMTP_SSL("smtp.qq.com", 465, timeout=timeout)
                # server.set_debuglevel(1)  # 启用 SMTP 调试日志
                
                # 登录
                self.log.info(f"尝试 {attempt}/{max_retries}：登录 {self.email}")
                server.login(self.email, self.auth_code)
                
                # 发送邮件
                self.log.info(f"尝试 {attempt}/{max_retries}：发送邮件到 {to}")
                server.sendmail(self.email, to, msg.as_string())
                self.log.success(f"邮件发送成功到 {to}")
                
                return True
                
            except (smtplib.SMTPException, OSError, socket.timeout, ConnectionError) as e:
                self.log.error(f"尝试 {attempt}/{max_retries} 失败: {e}")
                traceback.print_exc()
                if attempt < max_retries:
                    self.log.info(f"等待 5 秒后重试...")
                    time.sleep(5)
                    
            except Exception as e:
                # 捕获所有其他未预期的异常
                self.log.error(f"尝试 {attempt}/{max_retries} 发生未知错误: {e}")
                traceback.print_exc()
                if attempt < max_retries:
                    self.log.info(f"等待 5 秒后重试...")
                    time.sleep(5)
                    
            finally:
                if server is not None:
                    try:
                        self.log.info("关闭 SMTP 连接")
                        server.quit()
                    except Exception as e:
                        self.log.warning(f"关闭连接失败: {e}")
                # 重置 socket 超时
                socket.setdefaulttimeout(None)
        
        self.log.error("所有重试均失败")
        return False

if __name__ == "__main__":
    sender = QQSender("772166784@qq.com", "wdjvptwkfcpmbfie")
    sender.send("772166784@qq.com", "测试主题", "测试内容")