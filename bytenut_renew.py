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
        
        extend_button_xpath = "//button[contains(., 'Extend Time')]"
        # 回归最稳的单一选择器
        cf_iframe_selector = "iframe[src*='challenges.cloudflare.com']"

        # 🧹 核弹级清理底部隐私横幅，确保它绝对不会挡住鼠标
        print("🧹 尝试清理底部隐私横幅...")
        js_remove_banner = """
        var btns = document.querySelectorAll('button');
        for(var i=0; i<btns.length; i++) {
            if(btns[i].innerText.includes('Consent')) {
                btns[i].click();
                break;
            }
        }
        """
        sb.execute_script(js_remove_banner)
        sb.sleep(2)

        # 3. 🎯 严格等待续期按钮
        print("⏳ 正在严格等待续期按钮加载...")
        try:
            sb.wait_for_element_present(extend_button_xpath, timeout=20)
            print("✅ 续期按钮已加载。")
        except Exception:
            send_telegram_message(f"❌ 账号 {username} | 等待 20 秒仍未发现续期按钮。")
            sb.save_screenshot(f"timeout_no_btn_{username}.png")
            return

        # 📜 将按钮滚动到屏幕中央，顺便把上方的 CF 框拉进视野
        print("📜 正在将按钮滚动到屏幕中央可视区域...")
        scroll_js = f"""
        var ele = document.evaluate("{extend_button_xpath}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
        if(ele) {{ ele.scrollIntoView({{block: 'center'}}); }}
        """
        sb.execute_script(scroll_js)
        # 必须给 CF 框留出渲染时间
        sb.sleep(3) 

        # 4. 🛡️ 捕捉并物理点击 CF 验证码 (致敬前辈逻辑)
        print("🔍 启动雷达：等待 Cloudflare 验证码加载 (最长 15 秒)...")
        cf_exists = False
        try:
            sb.wait_for_element_present(cf_iframe_selector, timeout=15)
            cf_exists = True
            print("🎯 报告！成功捕捉到验证码框！")
        except:
            print("⚠️ 15秒扫描未发现验证码框。")

        if cf_exists:
            print("🖱️ 正在执行物理级鼠标轨迹模拟点击...")
            sb.sleep(1)
            try:
                # 方案 A：使用 SB 内置的最强反检测图形化点击
                sb.uc_gui_click_captcha()
            except:
                try:
                    # 方案 B：生成一条真实的物理鼠标轨迹并左键单击
                    sb.uc_click(cf_iframe_selector)
                except Exception as e:
                    print(f"⚠️ 物理点击出现波折，可能已成功: {e}")
            
            print("⏳ 死守人机验证 Token (最多轮询 30 秒)...")
            cf_passed = False
            for i in range(15): 
                sb.sleep(2)
                response_field = 'input[name="cf-turnstile-response"]'
                if sb.is_element_present(response_field):
                    token = sb.get_attribute(response_field, "value")
                    if token and len(token) > 10:
                        cf_passed = True
                        print(f"✅ 第 {i*2 + 2} 秒，成功截获 Token！CF 已破解！")
                        break
            
            if not cf_passed:
                print("⚠️ Token 获取超时。如果没报错，直接强攻续期按钮...")
                sb.save_screenshot(f"cf_wait_timeout_{username}.png")
        else:
            print("ℹ️ 未检测到验证码，确认为 CF 免检状态。")

        # 5. 🖱️ 最终点击续期按钮
        print("🖱️ 正在对续期按钮执行终极点击...")
        sb.js_click(extend_button_xpath)
        sb.sleep(6)
        
        send_telegram_message(f"✅ 账号 {username} | 续期指令执行完毕！")
        sb.save_screenshot(f"success_final_{username}.png")

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
