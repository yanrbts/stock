#!/bin/bash

SERVICE_NAME="stock"
INSTALL_DIR="/opt/stock"
SCRIPT_NAME="stock.py"
FILES="src/*"
REQ_FILE="requirements.txt"

echo "[*] Installing $SERVICE_NAME service..."

# 1. 创建安装目录
mkdir -p $INSTALL_DIR

# 2. 复制 Python 脚本和配置文件
cp $FILES $INSTALL_DIR/
cp $REQ_FILE $INSTALL_DIR/

# 3. 赋予执行权限
chmod +x $INSTALL_DIR/$SCRIPT_NAME

pip3 install --upgrade pip
pip3 install -r /opt/stock/requirements.txt

# 4. 创建 systemd 服务文件
cat <<EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service
[Unit]
Description=Stock Server
After=network.target

[Service]
ExecStart=/usr/bin/python3 $INSTALL_DIR/$SCRIPT_NAME -f 2 -s 17:00 -v 20:00
WorkingDirectory=$INSTALL_DIR
Restart=always
User=nobody
Group=nogroup
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$SERVICE_NAME
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 5. 重新加载 systemd 并启动服务
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "[*] Installation complete! You can check the service status using:"
echo "    systemctl status $SERVICE_NAME"
