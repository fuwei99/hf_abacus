---
title: Abacus Chat Proxy
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "3.9"
app_file: app.py
pinned: false
---

Check out the configuration reference at https://huggingface.co/docs/hub/spaces-config-reference

# Abacus Chat Proxy

一个用于中转API请求的代理服务器。

[![Deploy to Hugging Face Spaces](https://huggingface.co/datasets/huggingface/badges/raw/main/deploy-to-spaces-lg.svg)](https://huggingface.co/spaces/malt666/abacus_chat_proxy?duplicate=true)

## 🚀 快速开始

### Hugging Face一键部署

1. 点击上方的"Deploy to Hugging Face Spaces"按钮
2. 登录你的Hugging Face账号（如果还没有，需要注册一个）
3. 在弹出的页面中设置你的Space名称
4. 创建完Space后，在Space的Settings -> Repository Secrets中添加以下配置：
   - `covid_1`: 你的会话ID
   - `cookie_1`: 你的cookies字符串
   - `password`: （可选）访问密码
5. 等待自动部署完成即可

### 本地运行

#### Windows用户

1. 双击运行 `start.bat`
2. 首次运行选择 `0` 进行配置
3. 配置完成后选择 `Y` 直接启动，或 `N` 返回菜单
4. 之后可直接选择 `1` 启动代理
5. 代理服务器默认运行在 `http://127.0.0.1:9876/`

#### Linux/macOS用户

```bash
# 赋予脚本执行权限
chmod +x start.sh

# 运行脚本
./start.sh
```

选项说明同Windows。

### 🌐 Hugging Face部署

1. Fork本仓库到你的GitHub账号
2. 在Hugging Face上创建新的Space（选择Docker类型）
3. 在Space的设置中连接你的GitHub仓库
4. 在Space的设置中添加以下Secrets：
   - 第1组配置：
     - `covid_1`: 第1个会话ID
     - `cookie_1`: 第1个cookies字符串
   - 第2组配置（如果需要）：
     - `covid_2`: 第2个会话ID
     - `cookie_2`: 第2个cookies字符串
   - 更多配置以此类推（`covid_3`/`cookie_3`...）
   - `password`: （可选）访问密码
5. Space会自动部署，服务将在 `https://你的空间名-你的用户名.hf.space` 上运行

## ⚙️ 环境要求

- Python 3.8+
- pip

## 📦 依赖

```bash
Flask==3.1.0
requests==2.32.3
PyJWT==2.8.0
```

## 📝 配置说明

### 本地配置

首次运行时，请选择 `0` 进行配置，按照提示填写相关信息。配置文件将保存在 `config.json` 中。

### 环境变量配置

在Docker或云平台部署时，需要配置以下环境变量：

- 必需的配置（至少需要一组）：
  - `covid_1` + `cookie_1`: 第1组配置
  - `covid_2` + `cookie_2`: 第2组配置（可选）
  - 以此类推...
- 可选配置：
  - `password`: 访问密码

## 🔒 安全说明

- 配置文件中的敏感信息请妥善保管
- 建议在部署到Hugging Face时设置访问密码
- 不要将包含敏感信息的配置文件提交到公开仓库
- 在Hugging Face上配置时，请使用Secrets来存储敏感信息 