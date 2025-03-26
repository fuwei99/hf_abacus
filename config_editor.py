import json
import os
import hashlib

if __name__ == "__main__":
    config = None
    path = os.path.dirname(os.path.realpath(__file__))
    os.chdir(path)
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            config = json.load(f)
            try:
                config["config"]
            except KeyError:
                config = None
    if config is None:
        print(f"配置文件不存在或为空，创建新配置...")
        config = {"config": []}
        print(f"输入会话ID: ")
        user_data = {"conversation_id": input()}
        print(f"输入cookies: ")
        user_data["cookies"] = input()
        config["config"].append(user_data)
    
    again = True
    while True:
        if again:
            num = len(config["config"])
            print(f"\n当前有 {num} 个配置。")
        print("----------")
        print(f"1. 添加新配置")
        print(f"2. 删除所有配置")
        print(f"3. 设置密码")
        print(f"4. 保存并退出")
        choice = input()
        
        if choice == "1":
            print(f"输入会话ID: ")
            user_data = {"conversation_id": input()}
            print(f"输入cookies: ")
            user_data["cookies"] = input()
            config["config"].append(user_data)
            print("\n成功添加配置！")
            again = True
        
        elif choice == "2":
            print("确定要删除所有配置吗? (y/n)")
            if input().lower() == 'y':
                config["config"] = []
                print("已删除所有配置")
            again = True
        
        elif choice == "3":
            print(f"输入新密码（留空则删除密码）: ")
            password = input()
            with open("password.txt", "w") as f:
                if password != "":
                    f.write(hashlib.sha256(password.encode()).hexdigest())
                    print(f"密码已设置")
                else:
                    f.write("")
                    print(f"密码已删除")
        
        elif choice == "4":
            with open("config.json", "w") as f:
                json.dump(config, f, indent=4)
            print("配置已保存")
            break
        
        else:
            print(f"无效的选择")
            again = False
