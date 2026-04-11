import time
import ddddocr
import requests
import os
import sys
from datetime import datetime  # 👈 新增：用於取得執行時間
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from webdriver_manager.chrome import ChromeDriverManager

if getattr(sys, 'frozen', False):
    # 如果是從 PyInstaller 執行檔執行
    application_path = os.path.dirname(sys.executable)
else:
    # 如果是直接執行 .py 檔案
    application_path = os.path.dirname(os.path.abspath(__file__))

os.chdir(application_path)

class PeopleCount:
    def __init__(self):
        self.browser = self.create_browser()
        self.ocr = ddddocr.DdddOcr()
        self.base_url = 'https://www.chlife-stat.org/login.php'
        # 注意：這是網頁實際使用的「錯字版」網址
        self.export_url = 'https://www.chlife-stat.org/export_attendace_report.php'
        
        # 建立當次執行的資料夾名稱 (格式: 20260410_171530)
        self.run_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_folder = f"exports_{self.run_time_str}"
        
        self.target_meetings = {
            '主日': '37',
            '禱告': '40',
            '小排': '39',
            '晨興': '2026'
        }

    def create_browser(self):
        options = Options()
        options.add_argument('--headless') 
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        return driver

    def login(self):
        """登入邏輯，包含驗證碼識別與自動重試"""
        for attempt in range(5):
            print(f"\n嘗試登入第 {attempt + 1} 次...")
            self.browser.get(self.base_url)
            time.sleep(2)

            try:
                Select(self.browser.find_element(By.ID, 'district')).select_by_visible_text('台北市召會')
                time.sleep(0.5)
                Select(self.browser.find_element(By.ID, 'church')).select_by_visible_text('台北市召會第八十一會所')
                
                self.browser.find_element(By.ID, 'account').send_keys('h81s2')
                self.browser.find_element(By.ID, 'pwd').send_keys('h81')

                captcha_element = self.browser.find_element(By.ID, 'captcha')
                captcha_element.screenshot('captcha_temp.png')

                with open('captcha_temp.png', 'rb') as f:
                    captcha_code = self.ocr.classification(f.read())
                    print(f"🤖 AI 識別驗證碼：{captcha_code}")

                self.browser.find_element(By.ID, 'captcha_code').send_keys(captcha_code)
                self.browser.find_element(By.ID, 'login').click()
                
                time.sleep(3)
                
                if "login.php" not in self.browser.current_url:
                    print("✅ 成功登入！")
                    return True
            except Exception as e:
                print(f"⚠️ 登入過程發生異常: {e}")
            
            print("❌ 登入失敗，重新嘗試...")
        return False

    def export_excel(self, session, y_from, m_from, y_to, m_to, m_name, m_id):
        """執行單一報表的下載"""
        print(f"📡 正在匯出「{m_name}」報表...")
        
        params = {
            "start": "",
            "meeting": m_id,
            "search": "搜尋",
            "search_col": "member_name",
            "year_from": str(y_from),
            "month_from": str(m_from),
            "year_to": str(y_to),
            "month_to": str(m_to),
            "limit": "5000", 
            "churches[]": "0,0"
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://www.chlife-stat.org/attendance_report.php"
        }

        response = session.get(self.export_url, params=params, headers=headers)
        
        if response.status_code == 200:
            # 使用初始化時設定好的執行時間資料夾
            if not os.path.exists(self.output_folder):
                os.makedirs(self.output_folder)
                
            filename = f"{self.output_folder}/{m_name}_{y_from}{m_from}_{y_to}{m_to}.xls"
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"🟢 儲存成功: {filename}")
        else:
            print(f"🔴 {m_name} 匯出失敗 (HTTP {response.status_code})")

    def run(self):
        # 1. 使用者輸入區間
        print("\n--- 召會生活統計匯出工具 ---")
        y_from = input("請輸入開始年份 (例如 2026): ")
        m_from = input("請輸入開始月份 (例如 3): ")
        y_to = input("請輸入結束年份 (例如 2026): ")
        m_to = input("請輸入結束月份 (例如 4): ")

        # 2. 執行登入
        if self.login():
            session = requests.Session()
            for cookie in self.browser.get_cookies():
                session.cookies.set(cookie['name'], cookie['value'])

            # 3. 迴圈匯出四張報表
            for name, mid in self.target_meetings.items():
                self.export_excel(session, y_from, m_from, y_to, m_to, name, mid)
            
            print(f"\n✨ 所有報表已完成，儲存於資料夾: {self.output_folder}")
        
        self.browser.quit()

if __name__ == '__main__':
    pc = PeopleCount()
    pc.run()