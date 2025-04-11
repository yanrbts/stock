# email_sender.py
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from log import CPrint  # 假设你有一个 log.py 文件定义了 CPrint

class EmailSender:
    def __init__(self, sender_email, sender_password, receiver_email, smtp_server="smtp.gmail.com", smtp_port=587):
        self.sender_email = sender_email
        self.sender_password = sender_password  # 对于 Gmail，使用应用专用密码
        self.receiver_email = receiver_email
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.log = CPrint()

    def send_email(self, subject, body):
        """发送邮件"""
        # 创建邮件内容
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['From'] = Header(self.sender_email)
        msg['To'] = Header(self.receiver_email)
        msg['Subject'] = Header(subject, 'utf-8')

        try:
            # 连接 SMTP 服务器
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()  # 启用 TLS
            server.login(self.sender_email, self.sender_password)
            server.sendmail(self.sender_email, self.receiver_email, msg.as_string())
            server.quit()
            self.log.success(f"邮件发送成功到 {self.receiver_email}")
        except Exception as e:
            self.log.error(f"邮件发送失败: {e}")