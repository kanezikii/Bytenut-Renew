import os
import json
import time
import requests
from seleniumbase import SB

# ================= 配置与环境变量解析 =================

BYTENUT_ACCOUNTS = os.environ.get('BYTENUT_ACCOUNTS', '[]')
try:
    ACCOUNTS = json.loads(BYTENUT_ACCOUNTS)
except json.JSONDecodeError:
    print("❌ BYTENUT_ACCOUNTS 解析失败！")
    ACCOUNTS = []

TG_BOT = os.environ.get('TG_BOT', '')
USE_PROXY = os.environ.get('GOST_PROXY') != ''
PROXY_STR = "http://127.0.0.1:8080" if USE_PROXY else None

def send_telegram_message(message):
    print(message)
    if not TG_BOT or ',' not in TG_BOT:
        return
    try:
        token, chat_id = TG_BOT.split(',', 1)
        url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
        payload = {"chat_id": chat_id.strip(), "text": message, "parse_mode": "HTML"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"⚠️ Telegram 消息发送失败: {e}")

# ================= 核心自动化逻辑 =================

def login_and_renew(sb, account_info):
    username = account_info.get('username')
    password = account_info.get('password')
    panel_url = account_info.get('panel_url')
    
    send_telegram_message(f"🔄 开始处理账号: <b>{username}</b>")

    try:
        # 1. 登录
        print("🔑 使用账号密码登录...")
        sb.open("https://bytenut.com/auth/login")
        sb.sleep(3)
        sb.type('input[placeholder="Username"]', username)
        sb.type('input[placeholder="Password"]', password)
        sb.click('button:contains("Sign In")')
        sb.sleep(8) 

        if "/auth/login" in sb.get_current_url():
            send_telegram_message(f"❌ 账号 {username} 密码登录失败。")
            sb.save_screenshot(f"login_failed_{username}.png")
            return

        if not panel_url:
            print("⚠️ 缺少 panel_url 配置。")
            return

        # 2. 打开面板页面
        print(f"🎯 跳转至目标面板: {panel_url}")
        sb.open(panel_url)
        sb.sleep(5)

        # 强制向下深层滚动，触发懒加载组件
        print("📜 正在向下滚动页面以触发所有组件加载...")
        sb.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.8);")
        sb.sleep(4)

        # 3. 🛡️ 柔性处理 CF 验证码
        cf_iframe_selector = 'iframe[src*="cloudflare"]'
        extend_button_selector = 'button:contains("Extend Time")'

        print("🔍 查找 Cloudflare 验证码组件 (最多等待10秒)...")
        try:
            sb.wait_for_element_present(cf_iframe_selector, timeout=10)
            
            cf_element = sb.find_element(cf_iframe_selector)
            sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", cf_element)
            sb.sleep(2)
            
            print("🛡️ 捕捉到验证码框，尝试模拟点击...")
            try:
                sb.uc_gui_click_captcha()
            except:
                try:
                    sb.uc_click(cf_iframe_selector)
                except:
                    sb.js_click(cf_iframe_selector)
            
            print("⏳ 正在等待人机验证 Token...")
            cf_passed = False
            for _ in range(12): 
                sb.sleep(2)
                response_field = 'input[name="cf-turnstile-response"]'
                if sb.is_element_present(response_field):
                    token = sb.get_attribute(response_field, "value")
                    if token and len(token) > 10:
                        cf_passed = True
                        break
            
            if cf_passed:
                print("✅ 人机验证已成功！")
            else:
                print("⚠️ Token 获取超时，将继续尝试点击续期...")
                
        except Exception:
            print("⚠️ 未找到可见的 CF 验证码框。可能被直接放行，准备直接点击续期...")

        # 4. 点击续期 (✨ V9 核心修复区 ✨)
        print("🔍 查找并点击续期按钮...")
        try:
            # 等待按钮出现在源码中
            sb.wait_for_element_present(extend_button_selector, timeout=10)
            # 获取元素的实体对象
            btn_element = sb.find_element(extend_button_selector)
            
            # 将实体对象滚动到中心
            sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_element)
            sb.sleep(2)
            
            print("🖱️ 针对元素实体发起原生 JS 点击...")
            # 避开选择器解析，直接让浏览器点击这个实体对象
            sb.execute_script("arguments[0].click();", btn_element)
            sb.sleep(6)
            
            send_telegram_message(f"✅ 账号 {username} | 续期点击指令执行完毕！")
            sb.save_screenshot(f"success_final_{username}.png")
            
        except Exception as e:
            send_telegram_message(f"❌ 账号 {username} | 找不到续期按钮。")
            sb.save_screenshot(f"no_btn_{username}.png")
            print(f"详细错误: {e}")

    except Exception as e:
        error_screenshot = f"error_{username}_{int(time.time())}.png"
        sb.save_screenshot(error_screenshot)
        send_telegram_message(f"❌ 账号 {username} 发生异常: {str(e)[:100]}")

def main():
    if not ACCOUNTS:
        return

    with SB(uc=True, headless=False, proxy=PROXY_STR) as sb:
        for account in ACCOUNTS:
            login_and_renew(sb, account)
            sb.sleep(3)

if __name__ == "__main__":
    main()
