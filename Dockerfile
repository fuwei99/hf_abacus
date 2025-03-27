FROM python:3.11-slim

# 设置用户为root
USER root

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 设置环境变量
ENV HOST=0.0.0.0
ENV PORT=7860

# 删除敏感文件
RUN rm -f config.json password.txt

# 暴露端口（Hugging Face默认使用7860端口）
EXPOSE 7860

# 启动命令
CMD ["python", "app.py"] 