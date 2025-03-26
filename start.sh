#!/bin/bash

# 设置错误时退出
set -e

# 检查Python是否安装
echo "检查Python版本..."
if ! command -v python3 &> /dev/null; then
    echo "未找到Python。请安装Python 3并确保其在PATH中。"
    exit 1
fi

# 检查pip是否安装
echo "检查pip版本..."
if ! command -v pip3 &> /dev/null; then
    echo "未找到pip。请安装pip。"
    exit 1
fi

# 创建虚拟环境（如果不存在）
echo "检查虚拟环境..."
if [ ! -d "venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "激活虚拟环境..."
source venv/bin/activate || {
    echo "激活虚拟环境失败，尝试在全局环境安装依赖..."
}

# 安装依赖
echo "安装依赖..."
pip install -r requirements.txt || {
    echo "安装依赖失败。请检查网络连接并重试。"
    exit 1
}

echo "依赖安装完成。"

# 菜单函数
show_menu() {
    clear
    echo "================================"
    echo "        Abacus Chat Proxy"
    echo "================================"
    echo "[0] 配置代理 (运行config_editor)"
    echo "[1] 启动代理 (运行app.py)"
    echo "================================"
}

# 启动代理函数
start_proxy() {
    echo "启动代理服务器..."
    python app.py || {
        echo "代理服务器启动失败，请检查错误信息。"
        exit 1
    }
}

# 主循环
while true; do
    show_menu
    read -p "请选择操作 (0/1): " choice
    
    case $choice in
        0)
            echo "启动配置程序..."
            python config_editor.py || {
                echo "配置程序运行失败，请检查错误信息。"
                exit 1
            }
            echo "配置完成，是否要立即启动代理？(Y/N)"
            read -p "输入选择: " start_proxy_choice
            case $start_proxy_choice in
                [Yy]*)
                    start_proxy
                    break
                    ;;
                *)
                    continue
                    ;;
            esac
            ;;
        1)
            start_proxy
            break
            ;;
        *)
            echo "无效的选择，请重试！"
            sleep 2
            ;;
    esac
done

# 捕获中断信号（Ctrl+C）和终止信号
trap "exit" INT TERM 