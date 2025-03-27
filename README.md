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

> 📢 本项目基于 [orbitoo/abacus_chat_proxy](https://github.com/orbitoo/abacus_chat_proxy) 改进
> 
> 特别感谢 orbitoo 大佬提供的原始项目！
> 
> 本项目增加了：Docker部署支持、Hugging Face一键部署、自动保活功能等

一个用于中转API请求的代理服务器。

#### 注意创建space的时候把private改为public，因为不改为public导致的错误别来找我

[![Deploy to Hugging Face Spaces](https://huggingface.co/datasets/huggingface/badges/raw/main/deploy-to-spaces-lg.svg)](https://huggingface.co/spaces/malt666/abacus_chat_proxy?duplicate=true)

## ⚠️ 警告

**本地部署方式已失效！**为了适配hugging face，本项目的本地部署方式已不再可用。目前只能通过Hugging Face Spaces部署来使用本代理服务。请使用下方的Hugging Face一键部署方法。

## 🚀 快速开始

### Hugging Face一键部署

#### 注意创建space的时候把private改为public，因为不改为public导致的错误别来找我

1. 点击上方的"Deploy to Hugging Face Spaces"按钮
2. 登录你的Hugging Face账号（如果还没有，需要注册一个）
3. 在弹出的页面中设置你的Space名称，注意创建space的时候把private改为public，因为不改为为public导致的错误别来找我
4. 创建完Space后，在Space的Settings -> Repository Secrets中添加以下配置：
   - `cookie_1`: 你的cookies字符串
   - `password`: （必填，最好超过8位数，不然被盗用api导致点数用光，损失自负）api调用密码，也是dashboard登录密码
5. 等待自动部署完成即可
6. 登录dashboard查看使用情况，space里面是没办法登录的，点击弹出的登录页面的小窗口提示“请点击 https://xyz-abacus-chat-proxy.hf.space 来登录并查看使用情况”的链接来登录，登录密码是你设置的password
7. **获取API链接**：部署成功后，网络的登录页面会显示api接口链接；或者你点击右上角的三个点按钮，在弹出的选项卡里面点击"Embed this Space"，然后在弹出的"Embed this Space"界面里的"Direct URL"就是你的访问链接，你可以用这个链接调用API和查看使用情况
8. api调用：api调用的时候注意密钥填写你的password，不然没办法调用
### 本地运行（已失效）

> ⚠️ 以下本地运行方法已失效，仅作参考。请使用Hugging Face部署方式。

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
     - `cookie_1`: 第1个cookies字符串
   - 第2组配置（如果需要）：
     - `cookie_2`: 第2个cookies字符串
   - 更多配置以此类推（`cookie_3`...）
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
  - `cookie_1`: 第1组配置
  - `cookie_2`: 第2组配置（可选）
  - 以此类推...
- 可选配置：
  - `password`: 访问密码

## 🔒 安全说明

- 建议在部署到Hugging Face时设置访问密码
- 在Hugging Face上配置时，请使用Secrets来存储敏感信息 
