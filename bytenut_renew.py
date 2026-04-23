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
        sb.sleep(6)

        # 🌟 关键修复 1：向下滚动页面一段距离，确保组件进入可视区域
        print("📜 页面向下滚动，寻找验证码和按钮...")
        sb.execute_script("window.scrollBy(0, 600);")
        sb.sleep(2)

        # 3. 🛡️ 破解 CF 验证码
        cf_iframe_selector = 'iframe[src*="challenges.cloudflare.com"]'
        
        if sb.is_element_visible(cf_iframe_selector):
            # 将验证码框滚动到屏幕正中央
            sb.scroll_into_view(cf_iframe_selector)
            sb.sleep(1)
            
            print("🛡️ 发现 Cloudflare 验证码，尝试点击...")
            try:
                # 优先使用 SB 内置的专门针对验证码的点击防屏蔽方法
                sb.uc_gui_click_captcha() 
            except Exception:
                # 备选的真实物理点击
                sb.uc_click(cf_iframe_selector)
            
            # 轮询等待打勾验证通过 (最长等待 20 秒)
            print("⏳ 等待 CF 验证通过...")
            verification_passed = False
            for _ in range(10):
                sb.sleep(2)
                # 切入 iframe 检查状态
                try:
                    sb.switch_to_frame(cf_iframe_selector)
                    if sb.is_element_visible('#success-icon') or sb.is_element_visible('.cf-success'):
                        verification_passed = True
                        sb.switch_to_default_content()
                        break
                    sb.switch_to_default_content()
                except:
                    sb.switch_to_default_content()
            
            if verification_passed:
                print("✅ CF 验证已通过！")
            else:
                print("⚠️ CF 验证状态未知或超时，将强制尝试点击续期按钮...")
                sb.save_screenshot(f"cf_timeout_{username}.png")

        # 🌟 关键修复 2：将续期按钮滚动到可视区域内再点击
        extend_button_selector = 'button:contains("Extend Time")'
        if sb.is_element_present(extend_button_selector):
            # 确保按钮在屏幕中央
            sb.scroll_into_view(extend_button_selector)
            sb.sleep(1)
            
            print("🖱️ 点击续期按钮...")
            # 使用原生点击（更拟人）
            sb.click(extend_button_selector)
            sb.sleep(5)
            
            send_telegram_message(f"✅ {username} | 续期请求发送完毕！")
            sb.save_screenshot(f"success_{username}.png")
        else:
            send_telegram_message(f"ℹ️ {username} | 未找到续期按钮。")
            sb.save_screenshot(f"no_button_{username}.png")

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
