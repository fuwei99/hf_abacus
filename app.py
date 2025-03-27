from flask import Flask, request, jsonify, Response, render_template_string, render_template, redirect, url_for, session as flask_session
import requests
import time
import json
import uuid
import random
import io
import re
from functools import wraps
import hashlib
import jwt  
import os
import threading
from datetime import datetime, timedelta
import tiktoken  # 导入tiktoken来计算token数量

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get("SECRET_KEY", "abacus_chat_proxy_secret_key")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)


API_ENDPOINT_URL = "https://abacus.ai/api/v0/describeDeployment"
MODEL_LIST_URL = "https://abacus.ai/api/v0/listExternalApplications"
CHAT_URL = "https://apps.abacus.ai/api/_chatLLMSendMessageSSE"
USER_INFO_URL = "https://abacus.ai/api/v0/_getUserInfo"
COMPUTE_POINTS_URL = "https://apps.abacus.ai/api/_getOrganizationComputePoints"
COMPUTE_POINTS_LOG_URL = "https://abacus.ai/api/v0/_getOrganizationComputePointLog"


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
]


PASSWORD = None
USER_NUM = 0
USER_DATA = []
CURRENT_USER = -1
MODELS = set()


TRACE_ID = "3042e28b3abf475d8d973c7e904935af"
SENTRY_TRACE = f"{TRACE_ID}-80d9d2538b2682d0"


# 添加一个计数器记录健康检查次数
health_check_counter = 0


# 添加统计变量
model_usage_stats = {}  # 模型使用次数统计
total_tokens = {
    "prompt": 0,       # 输入token统计
    "completion": 0,   # 输出token统计
    "total": 0         # 总token统计
}

# 模型调用记录
model_usage_records = []  # 每次调用详细记录
MODEL_USAGE_RECORDS_FILE = "model_usage_records.json"  # 调用记录保存文件

# 计算点信息
compute_points = {
    "left": 0,          # 剩余计算点
    "total": 0,         # 总计算点
    "used": 0,          # 已使用计算点
    "percentage": 0,    # 使用百分比
    "last_update": None # 最后更新时间
}

# 计算点使用日志
compute_points_log = {
    "columns": {},      # 列名
    "log": []           # 日志数据
}

# 多用户计算点信息
users_compute_points = []

# 记录启动时间
START_TIME = datetime.utcnow() + timedelta(hours=8)  # 北京时间


# 自定义JSON编码器，处理datetime对象
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S')
        return super(DateTimeEncoder, self).default(obj)


# 加载模型调用记录
def load_model_usage_records():
    global model_usage_records
    try:
        if os.path.exists(MODEL_USAGE_RECORDS_FILE):
            with open(MODEL_USAGE_RECORDS_FILE, 'r', encoding='utf-8') as f:
                records = json.load(f)
                if isinstance(records, list):
                    model_usage_records = records
                    print(f"成功加载 {len(model_usage_records)} 条模型调用记录")
                else:
                    print("调用记录文件格式不正确，初始化为空列表")
    except Exception as e:
        print(f"加载模型调用记录失败: {e}")
        model_usage_records = []

# 保存模型调用记录
def save_model_usage_records():
    try:
        with open(MODEL_USAGE_RECORDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(model_usage_records, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
        print(f"成功保存 {len(model_usage_records)} 条模型调用记录")
    except Exception as e:
        print(f"保存模型调用记录失败: {e}")


def resolve_config():
    # 从环境变量读取多组配置
    config_list = []
    i = 1
    while True:
        covid = os.environ.get(f"covid_{i}")
        cookie = os.environ.get(f"cookie_{i}")
        if not (covid and cookie):
            break
        config_list.append({
            "conversation_id": covid,
            "cookies": cookie
        })
        i += 1
    
    # 如果环境变量存在配置，使用环境变量的配置
    if config_list:
        return config_list
    
    # 如果环境变量不存在，从文件读取
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
        config_list = config.get("config")
        return config_list
    except FileNotFoundError:
        print("未找到config.json文件")
        return []
    except json.JSONDecodeError:
        print("config.json格式错误")
        return []


def get_password():
    global PASSWORD
    # 从环境变量读取密码
    env_password = os.environ.get("password")
    if env_password:
        PASSWORD = hashlib.sha256(env_password.encode()).hexdigest()
        return

    # 如果环境变量不存在，从文件读取
    try:
        with open("password.txt", "r") as f:
            PASSWORD = f.read().strip()
    except FileNotFoundError:
        with open("password.txt", "w") as f:
            PASSWORD = None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not PASSWORD:
            return f(*args, **kwargs)
        
        # 检查Flask会话是否已登录
        if flask_session.get('logged_in'):
            return f(*args, **kwargs)
            
        # 如果是API请求，检查Authorization头
        auth = request.authorization
        if not auth or not check_auth(auth.token):
            # 如果是浏览器请求，重定向到登录页面
            if request.headers.get('Accept', '').find('text/html') >= 0:
                return redirect(url_for('login'))
            return jsonify({"error": "Unauthorized access"}), 401
        return f(*args, **kwargs)

    return decorated


def check_auth(token):
    return hashlib.sha256(token.encode()).hexdigest() == PASSWORD


def is_token_expired(token):
    if not token:
        return True
    
    try:
        # Malkodi tokenon sen validigo de subskribo
        payload = jwt.decode(token, options={"verify_signature": False})
        # Akiru eksvalidiĝan tempon, konsideru eksvalidiĝinta 5 minutojn antaŭe
        return payload.get('exp', 0) - time.time() < 300
    except:
        return True


def refresh_token(session, cookies):
    """Uzu kuketon por refreŝigi session token, nur revenigu novan tokenon"""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "reai-ui": "1",
        "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "x-abacus-org-host": "apps",
        "user-agent": random.choice(USER_AGENTS),
        "origin": "https://apps.abacus.ai",
        "referer": "https://apps.abacus.ai/",
        "cookie": cookies
    }
    
    try:
        response = session.post(
            USER_INFO_URL,
            headers=headers,
            json={},
            cookies=None
        )
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get('success') and 'sessionToken' in response_data.get('result', {}):
                return response_data['result']['sessionToken']
            else:
                print(f"刷新token失败: {response_data.get('error', '未知错误')}")
                return None
        else:
            print(f"刷新token失败，状态码: {response.status_code}")
            return None
    except Exception as e:
        print(f"刷新token异常: {e}")
        return None


def get_model_map(session, cookies, session_token):
    """Akiru disponeblan modelan liston kaj ĝiajn mapajn rilatojn"""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "reai-ui": "1",
        "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "x-abacus-org-host": "apps",
        "user-agent": random.choice(USER_AGENTS),
        "origin": "https://apps.abacus.ai",
        "referer": "https://apps.abacus.ai/",
        "cookie": cookies
    }
    
    if session_token:
        headers["session-token"] = session_token
    
    model_map = {}
    models_set = set()
    
    try:
        response = session.post(
            MODEL_LIST_URL,
            headers=headers,
            json={},
            cookies=None
        )
        
        if response.status_code != 200:
            print(f"获取模型列表失败，状态码: {response.status_code}")
            raise Exception("API请求失败")
        
        data = response.json()
        if not data.get('success'):
            print(f"获取模型列表失败: {data.get('error', '未知错误')}")
            raise Exception("API返回错误")
        
        applications = []
        if isinstance(data.get('result'), dict):
            applications = data.get('result', {}).get('externalApplications', [])
        elif isinstance(data.get('result'), list):
            applications = data.get('result', [])
        
        for app in applications:
            app_name = app.get('name', '')
            app_id = app.get('externalApplicationId', '')
            prediction_overrides = app.get('predictionOverrides', {})
            llm_name = prediction_overrides.get('llmName', '') if prediction_overrides else ''
            
            if not (app_name and app_id and llm_name):
                continue
                
            model_name = app_name
            model_map[model_name] = (app_id, llm_name)
            models_set.add(model_name)
        
        if not model_map:
            raise Exception("未找到任何可用模型")
        
        return model_map, models_set
    
    except Exception as e:
        print(f"获取模型列表异常: {e}")
        raise


def init_session():
    get_password()
    global USER_NUM, MODELS, USER_DATA
    config_list = resolve_config()
    user_num = len(config_list)
    all_models = set()
    
    for i in range(user_num):
        user = config_list[i]
        cookies = user.get("cookies")
        conversation_id = user.get("conversation_id")
        session = requests.Session()
        
        session_token = refresh_token(session, cookies)
        if not session_token:
            print(f"无法获取cookie {i+1}的token")
            continue
        
        try:
            model_map, models_set = get_model_map(session, cookies, session_token)
            all_models.update(models_set)
            USER_DATA.append((session, cookies, session_token, conversation_id, model_map))
        except Exception as e:
            print(f"配置用户 {i+1} 失败: {e}")
            continue
    
    USER_NUM = len(USER_DATA)
    if USER_NUM == 0:
        print("No user available, exiting...")
        exit(1)
    
    MODELS = all_models
    print(f"启动完成，共配置 {USER_NUM} 个用户")


def update_cookie(session, cookies):
    cookie_jar = {}
    for key, value in session.cookies.items():
        cookie_jar[key] = value
    cookie_dict = {}
    for item in cookies.split(";"):
        key, value = item.strip().split("=", 1)
        cookie_dict[key] = value
    cookie_dict.update(cookie_jar)
    cookies = "; ".join([f"{key}={value}" for key, value in cookie_dict.items()])
    return cookies


user_data = init_session()


@app.route("/v1/models", methods=["GET"])
@require_auth
def get_models():
    if len(MODELS) == 0:
        return jsonify({"error": "No models available"}), 500
    model_list = []
    for model in MODELS:
        model_list.append(
            {
                "id": model,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "Elbert",
                "name": model,
            }
        )
    return jsonify({"object": "list", "data": model_list})


@app.route("/v1/chat/completions", methods=["POST"])
@require_auth
def chat_completions():
    openai_request = request.get_json()
    stream = openai_request.get("stream", False)
    messages = openai_request.get("messages")
    if messages is None:
        return jsonify({"error": "Messages is required", "status": 400}), 400
    model = openai_request.get("model")
    if model not in MODELS:
        return (
            jsonify(
                {
                    "error": "Model not available, check if it is configured properly",
                    "status": 404,
                }
            ),
            404,
        )
    message = format_message(messages)
    think = (
        openai_request.get("think", False) if model == "Claude Sonnet 3.7" else False
    )
    return (
        send_message(message, model, think)
        if stream
        else send_message_non_stream(message, model, think)
    )


def get_user_data():
    global CURRENT_USER
    CURRENT_USER = (CURRENT_USER + 1) % USER_NUM
    print(f"使用配置 {CURRENT_USER+1}")
    
    # Akiru uzantajn datumojn
    session, cookies, session_token, conversation_id, model_map = USER_DATA[CURRENT_USER]
    
    # Kontrolu ĉu la tokeno eksvalidiĝis, se jes, refreŝigu ĝin
    if is_token_expired(session_token):
        print(f"Cookie {CURRENT_USER+1}的token已过期或即将过期，正在刷新...")
        new_token = refresh_token(session, cookies)
        if new_token:
            # Ĝisdatigu la globale konservitan tokenon
            USER_DATA[CURRENT_USER] = (session, cookies, new_token, conversation_id, model_map)
            session_token = new_token
            print(f"成功更新token: {session_token[:15]}...{session_token[-15:]}")
        else:
            print(f"警告：无法刷新Cookie {CURRENT_USER+1}的token，继续使用当前token")
    
    return (session, cookies, session_token, conversation_id, model_map)


def generate_trace_id():
    """Generu novan trace_id kaj sentry_trace"""
    trace_id = str(uuid.uuid4()).replace('-', '')
    sentry_trace = f"{trace_id}-{str(uuid.uuid4())[:16]}"
    return trace_id, sentry_trace


def send_message(message, model, think=False):
    """Flua traktado kaj plusendo de mesaĝoj"""
    (session, cookies, session_token, conversation_id, model_map) = get_user_data()
    trace_id, sentry_trace = generate_trace_id()
    
    # 计算输入token
    prompt_tokens = num_tokens_from_string(message)
    completion_buffer = io.StringIO()  # 收集所有输出用于计算token
    
    headers = {
        "accept": "text/event-stream",
        "accept-language": "zh-CN,zh;q=0.9",
        "baggage": f"sentry-environment=production,sentry-release=975eec6685013679c139fc88db2c48e123d5c604,sentry-public_key=3476ea6df1585dd10e92cdae3a66ff49,sentry-trace_id={trace_id}",
        "content-type": "text/plain;charset=UTF-8",
        "cookie": cookies,
        "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sentry-trace": sentry_trace,
        "user-agent": random.choice(USER_AGENTS)
    }
    
    if session_token:
        headers["session-token"] = session_token
    
    payload = {
        "requestId": str(uuid.uuid4()),
        "deploymentConversationId": conversation_id,
        "message": message,
        "isDesktop": False,
        "chatConfig": {
            "timezone": "Asia/Shanghai",
            "language": "zh-CN"
        },
        "llmName": model_map[model][1],
        "externalApplicationId": model_map[model][0],
        "regenerate": True,
        "editPrompt": True
    }
    
    if think:
        payload["useThinking"] = think
    
    try:
        response = session.post(
            CHAT_URL,
            headers=headers,
            data=json.dumps(payload),
            stream=True
        )
        
        response.raise_for_status()
        
        def extract_segment(line_data):
            try:
                data = json.loads(line_data)
                if "segment" in data:
                    if isinstance(data["segment"], str):
                        return data["segment"]
                    elif isinstance(data["segment"], dict) and "segment" in data["segment"]:
                        return data["segment"]["segment"]
                return ""
            except:
                return ""
        
        def generate():
            id = ""
            think_state = 2
            
            yield "data: " + json.dumps({"object": "chat.completion.chunk", "choices": [{"delta": {"role": "assistant"}}]}) + "\n\n"
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    try:
                        if think:
                            data = json.loads(decoded_line)
                            if data.get("type") != "text":
                                continue
                            elif think_state == 2:
                                id = data.get("messageId")
                                segment = "<think>\n" + data.get("segment", "")
                                completion_buffer.write(segment)  # 收集输出
                                yield f"data: {json.dumps({'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': segment}}]})}\n\n"
                                think_state = 1
                            elif think_state == 1:
                                if data.get("messageId") != id:
                                    segment = data.get("segment", "")
                                    completion_buffer.write(segment)  # 收集输出
                                    yield f"data: {json.dumps({'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': segment}}]})}\n\n"
                                else:
                                    segment = "\n</think>\n" + data.get("segment", "")
                                    completion_buffer.write(segment)  # 收集输出
                                    yield f"data: {json.dumps({'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': segment}}]})}\n\n"
                                    think_state = 0
                            else:
                                segment = data.get("segment", "")
                                completion_buffer.write(segment)  # 收集输出
                                yield f"data: {json.dumps({'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': segment}}]})}\n\n"
                        else:
                            segment = extract_segment(decoded_line)
                            if segment:
                                completion_buffer.write(segment)  # 收集输出
                                yield f"data: {json.dumps({'object': 'chat.completion.chunk', 'choices': [{'delta': {'content': segment}}]})}\n\n"
                    except Exception as e:
                        print(f"处理响应出错: {e}")
            
            yield "data: " + json.dumps({"object": "chat.completion.chunk", "choices": [{"delta": {}, "finish_reason": "stop"}]}) + "\n\n"
            yield "data: [DONE]\n\n"
            
            # 在流式传输完成后计算token并更新统计
            completion_tokens = num_tokens_from_string(completion_buffer.getvalue())
            update_model_stats(model, prompt_tokens, completion_tokens)
        
        return Response(generate(), mimetype="text/event-stream")
    except requests.exceptions.RequestException as e:
        error_details = str(e)
        if hasattr(e, 'response') and e.response is not None:
            if hasattr(e.response, 'text'):
                error_details += f" - Response: {e.response.text[:200]}"
        print(f"发送消息失败: {error_details}")
        return jsonify({"error": f"Failed to send message: {error_details}"}), 500


def send_message_non_stream(message, model, think=False):
    """Ne-flua traktado de mesaĝoj"""
    (session, cookies, session_token, conversation_id, model_map) = get_user_data()
    trace_id, sentry_trace = generate_trace_id()
    
    # 计算输入token
    prompt_tokens = num_tokens_from_string(message)
    
    headers = {
        "accept": "text/event-stream",
        "accept-language": "zh-CN,zh;q=0.9",
        "baggage": f"sentry-environment=production,sentry-release=975eec6685013679c139fc88db2c48e123d5c604,sentry-public_key=3476ea6df1585dd10e92cdae3a66ff49,sentry-trace_id={trace_id}",
        "content-type": "text/plain;charset=UTF-8",
        "cookie": cookies,
        "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "sentry-trace": sentry_trace,
        "user-agent": random.choice(USER_AGENTS)
    }
    
    if session_token:
        headers["session-token"] = session_token
    
    payload = {
        "requestId": str(uuid.uuid4()),
        "deploymentConversationId": conversation_id,
        "message": message,
        "isDesktop": False,
        "chatConfig": {
            "timezone": "Asia/Shanghai",
            "language": "zh-CN"
        },
        "llmName": model_map[model][1],
        "externalApplicationId": model_map[model][0],
        "regenerate": True,
        "editPrompt": True
    }
    
    if think:
        payload["useThinking"] = think
    
    try:
        response = session.post(
            CHAT_URL,
            headers=headers,
            data=json.dumps(payload),
            stream=True
        )
        
        response.raise_for_status()
        buffer = io.StringIO()
        
        def extract_segment(line_data):
            try:
                data = json.loads(line_data)
                if "segment" in data:
                    if isinstance(data["segment"], str):
                        return data["segment"]
                    elif isinstance(data["segment"], dict) and "segment" in data["segment"]:
                        return data["segment"]["segment"]
                return ""
            except:
                return ""
        
        if think:
            id = ""
            think_state = 2
            think_buffer = io.StringIO()
            content_buffer = io.StringIO()
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    try:
                        data = json.loads(decoded_line)
                        if data.get("type") != "text":
                            continue
                        elif think_state == 2:
                            id = data.get("messageId")
                            segment = data.get("segment", "")
                            think_buffer.write(segment)
                            think_state = 1
                        elif think_state == 1:
                            if data.get("messageId") != id:
                                segment = data.get("segment", "")
                                content_buffer.write(segment)
                            else:
                                segment = data.get("segment", "")
                                think_buffer.write(segment)
                                think_state = 0
                        else:
                            segment = data.get("segment", "")
                            content_buffer.write(segment)
                    except Exception as e:
                        print(f"处理响应出错: {e}")
            
            think_content = think_buffer.getvalue()
            response_content = content_buffer.getvalue()
            
            # 计算输出token并更新统计信息
            completion_tokens = num_tokens_from_string(think_content + response_content)
            update_model_stats(model, prompt_tokens, completion_tokens)
            
            return jsonify({
                "id": f"chatcmpl-{str(uuid.uuid4())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"<think>\n{think_content}\n</think>\n{response_content}"
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            })
        else:
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    segment = extract_segment(decoded_line)
                    if segment:
                        buffer.write(segment)
            
            response_content = buffer.getvalue()
            
            # 计算输出token并更新统计信息
            completion_tokens = num_tokens_from_string(response_content)
            update_model_stats(model, prompt_tokens, completion_tokens)
            
            return jsonify({
                "id": f"chatcmpl-{str(uuid.uuid4())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_content
                    },
                    "finish_reason": "stop"
                }],
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                }
            })
    except requests.exceptions.RequestException as e:
        error_details = str(e)
        if hasattr(e, 'response') and e.response is not None:
            if hasattr(e.response, 'text'):
                error_details += f" - Response: {e.response.text[:200]}"
        print(f"发送消息失败: {error_details}")
        return jsonify({"error": f"Failed to send message: {error_details}"}), 500


def format_message(messages):
    buffer = io.StringIO()
    role_map, prefix, messages = extract_role(messages)
    for message in messages:
        role = message.get("role")
        role = "\b" + role_map[role] if prefix else role_map[role]
        content = message.get("content").replace("\\n", "\n")
        pattern = re.compile(r"<\|removeRole\|>\n")
        if pattern.match(content):
            content = pattern.sub("", content)
            buffer.write(f"{content}\n")
        else:
            buffer.write(f"{role}: {content}\n\n")
    formatted_message = buffer.getvalue()
    return formatted_message


def extract_role(messages):
    role_map = {"user": "Human", "assistant": "Assistant", "system": "System"}
    prefix = False
    first_message = messages[0]["content"]
    pattern = re.compile(
        r"""
        <roleInfo>\s*
        user:\s*(?P<user>[^\n]*)\s*
        assistant:\s*(?P<assistant>[^\n]*)\s*
        system:\s*(?P<system>[^\n]*)\s*
        prefix:\s*(?P<prefix>[^\n]*)\s*
        </roleInfo>\n
    """,
        re.VERBOSE,
    )
    match = pattern.search(first_message)
    if match:
        role_map = {
            "user": match.group("user"),
            "assistant": match.group("assistant"),
            "system": match.group("system"),
        }
        prefix = match.group("prefix") == "1"
        messages[0]["content"] = pattern.sub("", first_message)
        print(f"Extracted role map:")
        print(
            f"User: {role_map['user']}, Assistant: {role_map['assistant']}, System: {role_map['system']}"
        )
        print(f"Using prefix: {prefix}")
    return (role_map, prefix, messages)


@app.route("/health", methods=["GET"])
def health_check():
    global health_check_counter
    health_check_counter += 1
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": health_check_counter
    })


def keep_alive():
    """每20分钟进行一次自我健康检查"""
    while True:
        try:
            requests.get("http://127.0.0.1:7860/health")
            time.sleep(1200)  # 20分钟
        except:
            pass  # 忽略错误，保持运行


@app.route("/", methods=["GET"])
def index():
    # 如果需要密码且用户未登录，重定向到登录页面
    if PASSWORD and not flask_session.get('logged_in'):
        return redirect(url_for('login'))
    
    # 否则重定向到仪表盘
    return redirect(url_for('dashboard'))


# 获取OpenAI的tokenizer来计算token数
def num_tokens_from_string(string, model="gpt-3.5-turbo"):
    """计算文本的token数量"""
    try:
        encoding = tiktoken.encoding_for_model(model)
        num_tokens = len(encoding.encode(string))
        print(f"使用tiktoken计算token数: {num_tokens}")
        return num_tokens
    except Exception as e:
        # 如果tiktoken不支持模型或者出错，使用简单的估算
        estimated_tokens = len(string) // 4  # 粗略估计每个token约4个字符
        print(f"使用估算方法计算token数: {estimated_tokens} (原因: {str(e)})")
        return estimated_tokens

# 更新模型使用统计
def update_model_stats(model, prompt_tokens, completion_tokens):
    global model_usage_stats, total_tokens, model_usage_records
    
    # 添加调用记录
    # 获取UTC时间
    utc_now = datetime.utcnow()
    # 转换为北京时间 (UTC+8)
    beijing_time = utc_now + timedelta(hours=8)
    call_time = beijing_time.strftime('%Y-%m-%d %H:%M:%S')  # 北京时间
    
    record = {
        "model": model,
        "call_time": call_time,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "calculation_method": "tiktoken" if any(x in model.lower() for x in ["gpt", "claude"]) or model in ["llama-3", "mistral", "gemma"] else "estimate"
    }
    model_usage_records.append(record)
    
    # 限制记录数量，保留最新的500条
    if len(model_usage_records) > 500:
        model_usage_records.pop(0)
    
    # 保存调用记录到本地文件
    save_model_usage_records()
    
    # 更新聚合统计
    if model not in model_usage_stats:
        model_usage_stats[model] = {
            "count": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    
    model_usage_stats[model]["count"] += 1
    model_usage_stats[model]["prompt_tokens"] += prompt_tokens
    model_usage_stats[model]["completion_tokens"] += completion_tokens
    model_usage_stats[model]["total_tokens"] += (prompt_tokens + completion_tokens)
    
    total_tokens["prompt"] += prompt_tokens
    total_tokens["completion"] += completion_tokens
    total_tokens["total"] += (prompt_tokens + completion_tokens)


# 获取计算点信息
def get_compute_points():
    global compute_points, USER_DATA, users_compute_points
    
    if USER_NUM == 0:
        return
    
    # 清空用户计算点列表
    users_compute_points = []
    
    # 累计总计算点
    total_left = 0
    total_points = 0
    
    # 获取每个用户的计算点信息
    for i, user_data in enumerate(USER_DATA):
        try:
            session, cookies, session_token, _, _ = user_data
            
            # 检查token是否有效
            if is_token_expired(session_token):
                session_token = refresh_token(session, cookies)
                if not session_token:
                    print(f"用户{i+1}刷新token失败，无法获取计算点信息")
                    continue
                USER_DATA[i] = (session, cookies, session_token, user_data[3], user_data[4])
            
            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "baggage": f"sentry-environment=production,sentry-release=93da8385541a6ce339b1f41b0c94428c70657e22,sentry-public_key=3476ea6df1585dd10e92cdae3a66ff49,sentry-trace_id={TRACE_ID}",
                "reai-ui": "1",
                "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": "\"Windows\"",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-origin",
                "sentry-trace": SENTRY_TRACE,
                "session-token": session_token,
                "x-abacus-org-host": "apps",
                "cookie": cookies
            }
            
            response = session.get(
                COMPUTE_POINTS_URL,
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success") and "result" in result:
                    data = result["result"]
                    left = data.get("computePointsLeft", 0)
                    total = data.get("totalComputePoints", 0)
                    used = total - left
                    percentage = round((used / total) * 100, 2) if total > 0 else 0
                    
                    # 获取北京时间
                    beijing_now = datetime.utcnow() + timedelta(hours=8)
                    
                    # 添加到用户列表
                    user_points = {
                        "user_id": i + 1,  # 用户ID从1开始
                        "left": left,
                        "total": total,
                        "used": used,
                        "percentage": percentage,
                        "last_update": beijing_now
                    }
                    users_compute_points.append(user_points)
                    
                    # 累计总数
                    total_left += left
                    total_points += total
                    
                    print(f"用户{i+1}计算点信息更新成功: 剩余 {left}, 总计 {total}")
                    
                    # 对于第一个用户，获取计算点使用日志
                    if i == 0:
                        get_compute_points_log(session, cookies, session_token)
                else:
                    print(f"获取用户{i+1}计算点信息失败: {result.get('error', '未知错误')}")
            else:
                print(f"获取用户{i+1}计算点信息失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"获取用户{i+1}计算点信息异常: {e}")
    
    # 更新全局计算点信息（所有用户总和）
    if users_compute_points:
        compute_points["left"] = total_left
        compute_points["total"] = total_points
        compute_points["used"] = total_points - total_left
        compute_points["percentage"] = round((compute_points["used"] / compute_points["total"]) * 100, 2) if compute_points["total"] > 0 else 0
        compute_points["last_update"] = datetime.utcnow() + timedelta(hours=8)  # 北京时间
        print(f"所有用户计算点总计: 剩余 {total_left}, 总计 {total_points}")

# 获取计算点使用日志
def get_compute_points_log(session, cookies, session_token):
    global compute_points_log
    
    try:
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json",
            "reai-ui": "1",
            "sec-ch-ua": "\"Chromium\";v=\"116\", \"Not)A;Brand\";v=\"24\", \"Google Chrome\";v=\"116\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "session-token": session_token,
            "x-abacus-org-host": "apps",
            "cookie": cookies
        }
        
        response = session.post(
            COMPUTE_POINTS_LOG_URL,
            headers=headers,
            json={"byLlm": True}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success") and "result" in result:
                data = result["result"]
                compute_points_log["columns"] = data.get("columns", {})
                compute_points_log["log"] = data.get("log", [])
                print(f"计算点使用日志更新成功，获取到 {len(compute_points_log['log'])} 条记录")
            else:
                print(f"获取计算点使用日志失败: {result.get('error', '未知错误')}")
        else:
            print(f"获取计算点使用日志失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"获取计算点使用日志异常: {e}")


# 添加登录相关路由
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        password = request.form.get("password")
        if password and hashlib.sha256(password.encode()).hexdigest() == PASSWORD:
            flask_session['logged_in'] = True
            flask_session.permanent = True
            return redirect(url_for('dashboard'))
        else:
            # 密码错误时提示使用环境变量密码
            error = "密码不正确。请使用设置的环境变量 password 或 password.txt 中的值作为密码和API认证密钥。"
    
    # 传递空间URL给模板
    return render_template('login.html', error=error, space_url=SPACE_URL)


@app.route("/logout")
def logout():
    flask_session.clear()
    return redirect(url_for('login'))


@app.route("/dashboard")
@require_auth
def dashboard():
    # 在每次访问仪表盘时更新计算点信息
    get_compute_points()
    
    # 计算运行时间（使用北京时间）
    beijing_now = datetime.utcnow() + timedelta(hours=8)
    uptime = beijing_now - START_TIME
    days = uptime.days
    hours, remainder = divmod(uptime.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        uptime_str = f"{days}天 {hours}小时 {minutes}分钟"
    elif hours > 0:
        uptime_str = f"{hours}小时 {minutes}分钟"
    else:
        uptime_str = f"{minutes}分钟 {seconds}秒"

    # 当前北京年份
    beijing_year = beijing_now.year

    return render_template(
        'dashboard.html',
        uptime=uptime_str,
        health_checks=health_check_counter,
        user_count=USER_NUM,
        models=sorted(list(MODELS)),
        year=beijing_year,
        model_stats=model_usage_stats,
        total_tokens=total_tokens,
        compute_points=compute_points,
        compute_points_log=compute_points_log,
        space_url=SPACE_URL,  # 传递空间URL
        users_compute_points=users_compute_points,  # 传递用户计算点信息
        model_usage_records=model_usage_records  # 传递模型使用记录
    )


# 获取Hugging Face Space URL
def get_space_url():
    # 尝试从环境变量获取
    space_url = os.environ.get("SPACE_URL")
    if space_url:
        return space_url
    
    # 如果SPACE_URL不存在，尝试从SPACE_ID构建
    space_id = os.environ.get("SPACE_ID")
    if space_id:
        username, space_name = space_id.split("/")
        return f"https://{username}-{space_name}.hf.space"
    
    # 如果以上都不存在，尝试从单独的用户名和空间名构建
    username = os.environ.get("SPACE_USERNAME")
    space_name = os.environ.get("SPACE_NAME")
    if username and space_name:
        return f"https://{username}-{space_name}.hf.space"
    
    # 默认返回None
    return None

# 获取空间URL
SPACE_URL = get_space_url()


if __name__ == "__main__":
    # 启动保活线程
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # 加载历史模型调用记录
    load_model_usage_records()
    
    # 获取初始计算点信息
    get_compute_points()
    
    port = int(os.environ.get("PORT", 9876))
    app.run(port=port, host="0.0.0.0")
