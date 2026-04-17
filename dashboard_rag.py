"""
81Y3-dashboard RAG 系統
專門處理 81Y3-dashboard 的資料，提供給 LINE Bot 使用
"""

import os
import re
import json
from typing import Optional, Dict
import google.generativeai as genai

# 81Y3-dashboard 路徑
DASHBOARD_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TREND_HTML_PATH = os.path.join(DASHBOARD_BASE_DIR, "trend.html")

# Gemini 配置
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
try:
    generation_config = {
        "temperature": 0,  # 設為 0 確保回答一致性
    }
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
    print("✅ Gemini 模型初始化成功")
except Exception as e:
    print(f"❌ Gemini 配置失敗: {e}")
    model = None


def extract_dashboard_data(html_path: str) -> Optional[Dict]:
    """
    從 trend.html 中提取所有資料
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 TREND_DATA - 使用更強健的匹配
        trend_match = re.search(r'const TREND_DATA = (\{[^;]+\});', content, re.DOTALL)
        if trend_match:
            try:
                trend_data = json.loads(trend_match.group(1))
                print(f"✅ 成功載入 TREND_DATA")
            except:
                trend_data = {}
        else:
            trend_data = {}
        
        # 提取 MEMBER_DATA
        member_match = re.search(r'const MEMBER_DATA = (\{[^;]+\});', content, re.DOTALL)
        if member_match:
            try:
                member_data = json.loads(member_match.group(1))
                print(f"✅ 成功載入 MEMBER_DATA")
            except:
                member_data = {}
        else:
            member_data = {}
        
        # 提取 BASE_DATA
        base_match = re.search(r'const BASE_DATA = (\{[^;]+\});', content, re.DOTALL)
        if base_match:
            try:
                base_data = json.loads(base_match.group(1))
                print(f"✅ 成功載入 BASE_DATA")
            except:
                base_data = {}
        else:
            base_data = {}
        
        # 提取 WEEK_META - 簡化處理，只提取週標籤
        week_meta = []
        week_match = re.findall(r'\{label:.*?month:.*?date:.*?\}', content, re.DOTALL)
        if week_match:
            try:
                for match in week_match:
                    # 使用正則提取各個欄位
                    label = re.search(r"label:'(W\d+)'", match)
                    month = re.search(r"month:'([^']+)'", match)
                    date = re.search(r"date:'([^']+)'", match)
                    if label and month and date:
                        week_meta.append({
                            'label': label.group(1),
                            'month': month.group(1),
                            'date': date.group(1)
                        })
                print(f"✅ 成功載入 WEEK_META ({len(week_meta)} 週)")
            except:
                week_meta = []
        else:
            week_meta = []
        
        # 提取 SCOPE_CONFIG
        scope_match = re.search(r'const SCOPE_CONFIG = (\{[^;]+\});', content, re.DOTALL)
        if scope_match:
            try:
                # 將單引號替換為雙引號以便 JSON 解析
                scope_json = scope_match.group(1).replace("'", '"')
                scope_config = json.loads(scope_json)
                print(f"✅ 成功載入 SCOPE_CONFIG")
            except:
                scope_config = {}
        else:
            scope_config = {}
        
        print(f"   - 區別數量: {len(trend_data.get('districts', {}))}")
        print(f"   - 成員總數: {sum(len(m) for m in member_data.values())}")
        
        return {
            'trend_data': trend_data,
            'member_data': member_data,
            'base_data': base_data,
            'week_meta': week_meta,
            'scope_config': scope_config
        }
    except Exception as e:
        print(f"❌ 讀取 trend.html 失敗: {e}")
        return None


def extract_html_text(html_path: str) -> str:
    """
    從 HTML 檔案中提取純文字內容（使用正則表達式）
    """
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 移除 script 和 style 標籤及其內容
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除所有 HTML 標籤
        content = re.sub(r'<[^>]+>', '', content)
        
        # 移除 HTML 實體編碼
        content = re.sub(r'&nbsp;', ' ', content)
        content = re.sub(r'&lt;', '<', content)
        content = re.sub(r'&gt;', '>', content)
        content = re.sub(r'&amp;', '&', content)
        
        # 清理空白行
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        return '\n'.join(lines)
    except Exception as e:
        print(f"⚠️ 讀取 {html_path} 文字內容失敗: {e}")
        return ""


def load_html_files_as_text(dashboard_dir: str) -> str:
    """
    載入主要 HTML 檔案的文字內容
    """
    context = ""
    html_files = [
        'trend.html',
        'index.html',
        'invite.html',
        'leaderboard.html',
        'weekly.html',
        'youth.html',
        'hs.html',
        'ms.html',
    ]
    
    for html_file in html_files:
        html_path = os.path.join(dashboard_dir, html_file)
        if os.path.exists(html_path):
            text_content = extract_html_text(html_path)
            if text_content:
                context += f"\n## 📄 {html_file} 內容\n\n"
                # 限制字數，避免太長
                if len(text_content) > 3000:
                    text_content = text_content[:3000] + "\n... (內容過長已截斷)"
                context += text_content + "\n"
    
    return context


def extract_weekly_data(weekly_html_path: str) -> Optional[Dict]:
    """
    從 weekly.html 中提取點名追蹤資料
    """
    try:
        with open(weekly_html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 DISTRICTS
        districts_match = re.search(r'const DISTRICTS = (\[.*?\]);', content, re.DOTALL)
        if districts_match:
            try:
                districts_json = districts_match.group(1).replace("'", '"')
                districts_data = json.loads(districts_json)
                print(f"✅ 成功載入 DISTRICTS ({len(districts_data)} 個區)")
            except:
                districts_data = []
        else:
            districts_data = []
        
        # 提取 MEMBERS - 使用更強健的匹配
        members_match = re.search(r'const MEMBERS = (\{.*?\});', content, re.DOTALL)
        if members_match:
            try:
                # 將單引號替換為雙引號
                members_json = members_match.group(1).replace("'", '"')
                members_data = json.loads(members_json)
                print(f"✅ 成功載入 MEMBERS ({sum(len(m) for m in members_data.values())} 位成員)")
            except:
                members_data = {}
        else:
            members_data = {}
        
        return {
            'districts': districts_data,
            'members': members_data
        }
    except Exception as e:
        print(f"⚠️ 讀取 weekly.html 失敗: {e}")
        return None


def format_weekly_data(weekly_data: Dict) -> str:
    """
    將週點名資料格式化為 markdown
    """
    if not weekly_data:
        return "無週點名資料"
    
    markdown = "## 📋 本週點名追蹤\n\n"
    
    districts = weekly_data.get('districts', [])
    members = weekly_data.get('members', {})
    
    district_names = {
        'y1': '青年一區', 'y2': '青年二區', 'y3': '青年三區',
        'hs1': '高中一區', 'hs2': '高中二區', 'hs3': '高中三區',
        'ms1': '國中一區', 'ms2': '國中二區'
    }
    
    for district in districts:
        district_id = district.get('id', '')
        district_name = district.get('name', district_names.get(district_id, district_id))
        total = district.get('total', 0)
        base = district.get('base', 0)
        pct = district.get('pct', 0)
        status = district.get('status', 'unknown')
        
        status_text = {
            'ok': '✅ 正常',
            'low': '⚠️ 偏低',
            'unsubmitted': '❌ 未提交'
        }.get(status, status)
        
        markdown += f"### {district_name} ({district_id.upper()})\n\n"
        markdown += f"- **本週出席**: {total} 人 (基數: {base}, 出席率: {pct}%)\n"
        markdown += f"- **狀態**: {status_text}\n"
        
        # 各排出席狀況
        rows = district.get('rows', [])
        if rows:
            markdown += "- **各排出席**:\n"
            for row in rows:
                row_name = row.get('name', '未分排') or '未分排'
                count = row.get('count', 0)
                markdown += f"  - {row_name}: {count} 人\n"
        
        # 其他活動出席
        extra = district.get('extra', {})
        if extra:
            markdown += "- **其他活動**:\n"
            for act_name, act_count in extra.items():
                markdown += f"  - {act_name}: {act_count} 人\n"
        
        # 未出席成員
        district_members = members.get(district_id, [])
        absent_members = [m for m in district_members if m.get('zero', False)]
        
        if absent_members:
            markdown += f"- **本週未出席成員** ({len(absent_members)} 人):\n"
            for m in absent_members:
                name = m.get('n', '未知')
                pai = m.get('pai', '未分排') or '未分排'
                hist = m.get('hist', 0)
                markdown += f"  - {name}（配搭: {pai}, 歷史出席率: {hist}%）\n"
        
        markdown += "\n"
    
    return markdown


def load_district_json_data(dashboard_dir: str) -> Dict[str, Dict]:
    """
    載入各小區的所有 JSON 資料
    """
    data = {}
    districts = ['y1', 'y2', 'y3', 'hs1', 'hs2', 'hs3', 'ms1', 'ms2']
    
    for district in districts:
        district_dir = os.path.join(dashboard_dir, district)
        if not os.path.exists(district_dir):
            continue
        
        data[district] = {}
        
        # 載入 people_data.json
        people_file = os.path.join(district_dir, 'people_data.json')
        if os.path.exists(people_file):
            try:
                with open(people_file, 'r', encoding='utf-8') as f:
                    data[district]['people'] = json.load(f)
            except Exception as e:
                print(f"⚠️ 讀取 {district}/people_data.json 失敗: {e}")
        
        # 載入 leaderboard.json
        leaderboard_file = os.path.join(district_dir, 'leaderboard.json')
        if os.path.exists(leaderboard_file):
            try:
                with open(leaderboard_file, 'r', encoding='utf-8') as f:
                    data[district]['leaderboard'] = json.load(f)
            except Exception as e:
                print(f"⚠️ 讀取 {district}/leaderboard.json 失敗: {e}")
        else:
            # 從 leaderboard.html 提取排行榜資料（如果沒有 JSON 檔案）
            leaderboard_html = os.path.join(district_dir, 'leaderboard.html')
            if os.path.exists(leaderboard_html):
                try:
                    with open(leaderboard_html, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # 提取 DATA 資料
                    data_match = re.search(r'const DATA = (\{.*?\});', html_content, re.DOTALL)
                    if data_match:
                        try:
                            data_json = data_match.group(1)
                            leaderboard_data = json.loads(data_json)
                            data[district]['leaderboard'] = leaderboard_data
                            print(f"✅ 從 {district}/leaderboard.html 提取排行榜資料 ({len(leaderboard_data.get('rankings', []))} 人)")
                        except:
                            pass
                except Exception as e:
                    print(f"⚠️ 讀取 {district}/leaderboard.html 失敗: {e}")
        
        # 載入 invite_data.json
        invite_file = os.path.join(district_dir, 'invite_data.json')
        if os.path.exists(invite_file):
            try:
                with open(invite_file, 'r', encoding='utf-8') as f:
                    data[district]['invite'] = json.load(f)
            except Exception as e:
                print(f"⚠️ 讀取 {district}/invite_data.json 失敗: {e}")
        
        # 載入 recoverable.json
        recoverable_file = os.path.join(district_dir, 'recoverable.json')
        if os.path.exists(recoverable_file):
            try:
                with open(recoverable_file, 'r', encoding='utf-8') as f:
                    data[district]['recoverable'] = json.load(f)
            except Exception as e:
                print(f"⚠️ 讀取 {district}/recoverable.json 失敗: {e}")
        
        # 從 invite.html 提取 RECOVERABLE 資料（如果沒有 JSON 檔案）
        if 'invite' not in data[district] or 'recoverable' not in data[district]:
            invite_html = os.path.join(district_dir, 'invite.html')
            if os.path.exists(invite_html):
                try:
                    with open(invite_html, 'r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    # 提取 RECOVERABLE 資料
                    recoverable_match = re.search(r'const RECOVERABLE = (\[.*?\]);', html_content, re.DOTALL)
                    if recoverable_match:
                        try:
                            recoverable_json = recoverable_match.group(1).replace("'", '"')
                            recoverable_data = json.loads(recoverable_json)
                            if 'invite' not in data[district]:
                                data[district]['invite'] = {}
                            data[district]['invite']['recoverable'] = recoverable_data
                            print(f"✅ 從 {district}/invite.html 提取 RECOVERABLE 資料 ({len(recoverable_data)} 人)")
                        except:
                            pass
                except Exception as e:
                    print(f"⚠️ 讀取 {district}/invite.html 失敗: {e}")
    
    print(f"✅ 成功載入 {len(data)} 個小區的 JSON 資料")
    return data


def format_trend_data(trend_data: Dict, week_meta: list) -> str:
    """
    將趨勢資料格式化為 markdown
    """
    if not trend_data or 'districts' not in trend_data:
        return "無趨勢資料"
    
    markdown = "## 📈 出席趨勢資料\n\n"
    
    # 檢查 week_meta 是否為空
    if week_meta and len(week_meta) > 0:
        markdown += f"**資料週期**: {week_meta[0]['month']} {week_meta[0]['date']} — {week_meta[-1]['month']} {week_meta[-1]['date']}\n\n"
    else:
        markdown += "**資料週期**: 未知\n\n"
    
    districts = trend_data['districts']
    
    for district_key, district_data in districts.items():
        markdown += f"### {district_key.upper()}\n\n"
        
        for activity, activity_data in district_data.items():
            markdown += f"**{activity}**:\n"
            
            # 顯示最近 4 週的數據
            for seg_key, values in activity_data.items():
                if not isinstance(values, list) or len(values) == 0:
                    continue
                    
                if seg_key == 'all':
                    recent = values[-4:] if len(values) >= 4 else values
                    markdown += f"- 全部: {recent}\n"
                elif seg_key in ['male', 'female']:
                    recent = values[-4:] if len(values) >= 4 else values
                    markdown += f"- {'弟兄' if seg_key == 'male' else '姊妹'}: {recent}\n"
                elif seg_key in ['daxue', 'qingzhi']:
                    recent = values[-4:] if len(values) >= 4 else values
                    markdown += f"- {'大學' if seg_key == 'daxue' else '青職'}: {recent}\n"
            
            markdown += "\n"
    
    return markdown


def format_member_data(member_data: Dict) -> str:
    """
    將成員資料格式化為 markdown
    """
    if not member_data:
        return "無成員資料"
    
    markdown = "## 👥 成員名單\n\n"
    
    district_names = {
        'y1': '青年一區', 'y2': '青年二區', 'y3': '青年三區',
        'hs1': '高中一區', 'hs2': '高中二區', 'hs3': '高中三區',
        'ms1': '國中一區', 'ms2': '國中二區'
    }
    
    for district_key, members in member_data.items():
        if not members:
            continue
        
        markdown += f"### {district_names.get(district_key, district_key)} ({len(members)} 人)\n\n"
        
        for member in members:
            gender_icon = '🙋' if member.get('g') == 'm' else '🙋‍♀️'
            age_label = '大學' if member.get('a') == 'd' else '青職' if member.get('a') == 'q' else member.get('a', '')
            markdown += f"- {gender_icon} **{member.get('n', '未知')}** ({age_label}, {member.get('r', '')})\n"
        
        markdown += "\n"
    
    return markdown


def format_base_data(base_data: Dict) -> str:
    """
    將基數資料格式化為 markdown
    """
    if not base_data:
        return "無基數資料"
    
    markdown = "## 📊 基數資料\n\n"
    
    district_names = {
        'y1': '青年一區', 'y2': '青年二區', 'y3': '青年三區',
        'hs1': '高中一區', 'hs2': '高中二區', 'hs3': '高中三區',
        'ms1': '國中一區', 'ms2': '國中二區',
        'youth': '青年大區', 'hs': '高中大區', 'ms': '國中大區',
        'church': '整個會所'
    }
    
    for key, value in base_data.items():
        name = district_names.get(key, key)
        markdown += f"- **{name}**: {value} 人\n"
    
    return markdown


def format_leaderboard_data(district_data: Dict) -> str:
    """
    將排行榜資料格式化為 markdown
    """
    if not district_data:
        return "無排行榜資料"
    
    markdown = "## 🏆 出席排行榜\n\n"
    
    district_names = {
        'y1': '青年一區', 'y2': '青年二區', 'y3': '青年三區',
        'hs1': '高中一區', 'hs2': '高中二區', 'hs3': '高中三區',
        'ms1': '國中一區', 'ms2': '國中二區'
    }
    
    for district_key, data in district_data.items():
        if 'leaderboard' not in data:
            continue
        
        leaderboard = data['leaderboard']
        period = leaderboard.get('period', '未知')
        rankings = leaderboard.get('rankings', [])
        
        markdown += f"### {district_names.get(district_key, district_key)} — {period}\n\n"
        
        for rank_info in rankings[:10]:  # 只顯示前 10 名
            name = rank_info.get('姓名', '未知')
            score = rank_info.get('score', 0)
            rank = rank_info.get('rank', 0)
            markdown += f"{rank}. **{name}** — {score} 分\n"
        
        markdown += "\n"
    
    return markdown


def format_invite_data(district_data: Dict) -> str:
    """
    將邀請/恢復資料格式化為 markdown
    """
    if not district_data:
        return "無邀請資料"
    
    markdown = "## 💌 邀請與恢復資料\n\n"
    
    district_names = {
        'y1': '青年一區', 'y2': '青年二區', 'y3': '青年三區',
        'hs1': '高中一區', 'hs2': '高中二區', 'hs3': '高中三區',
        'ms1': '國中一區', 'ms2': '國中二區'
    }
    
    for district_key, data in district_data.items():
        if 'invite' not in data:
            continue
        
        invite_info = data['invite']
        recoverable = invite_info.get('recoverable', [])
        irregular = invite_info.get('irregular', [])
        
        markdown += f"### {district_names.get(district_key, district_key)}\n\n"
        
        if recoverable:
            markdown += f"**可恢復成員** ({len(recoverable)} 人):\n"
            for person in recoverable[:5]:  # 只顯示前 5 名
                name = person.get('姓名', '未知')
                last_active = person.get('last_active_month', '未知')
                attendance = person.get('attendance_since_sep', 0)
                markdown += f"- {name}（最後活躍: {last_active}, 9月至今出席: {attendance}次）\n"
            if len(recoverable) > 5:
                markdown += f"... 還有 {len(recoverable) - 5} 人\n"
            markdown += "\n"
        
        if irregular:
            markdown += f"**不穩定成員** ({len(irregular)} 人):\n"
            for person in irregular:
                name = person.get('姓名', '未知')
                recent_4weeks = person.get('recent_4weeks', 0)
                attendance = person.get('attendance_since_sep', 0)
                markdown += f"- {name}（近4週出席: {recent_4weeks}次, 9月至今: {attendance}次）\n"
            markdown += "\n"
    
    return markdown


def format_recoverable_data(district_data: Dict) -> str:
    """
    將可恢復成員詳細資料格式化為 markdown
    """
    if not district_data:
        return "無可恢復資料"
    
    markdown = "## 🔙 可恢復成員詳細資料\n\n"
    
    district_names = {
        'y1': '青年一區', 'y2': '青年二區', 'y3': '青年三區',
        'hs1': '高中一區', 'hs2': '高中二區', 'hs3': '高中三區',
        'ms1': '國中一區', 'ms2': '國中二區'
    }
    
    for district_key, data in district_data.items():
        if 'recoverable' not in data:
            continue
        
        recoverable_info = data['recoverable']
        recoverable_list = recoverable_info.get('recoverable', [])
        irregular_list = recoverable_info.get('irregular', [])
        
        markdown += f"### {district_names.get(district_key, district_key)}\n\n"
        
        if recoverable_list:
            markdown += f"**長期缺席** ({len(recoverable_list)} 人):\n"
            for person in recoverable_list[:8]:  # 只顯示前 8 名
                name = person.get('姓名', '未知')
                sep_rate = person.get('sep_rate', 0)
                recent = person.get('recent', [])
                markdown += f"- {name}（缺席率: {sep_rate}%, 近4週: {recent}）\n"
            if len(recoverable_list) > 8:
                markdown += f"... 還有 {len(recoverable_list) - 8} 人\n"
            markdown += "\n"
        
        if irregular_list:
            markdown += f"**不穩定出席** ({len(irregular_list)} 人):\n"
            for person in irregular_list:
                name = person.get('姓名', '未知')
                sep_rate = person.get('sep_rate', 0)
                recent = person.get('recent', [])
                recent_count = person.get('recent_count', 0)
                markdown += f"- {name}（缺席率: {sep_rate}%, 近4週出席: {recent_count}次, 狀態: {recent}）\n"
            markdown += "\n"
    
    return markdown


def generate_rag_context() -> str:
    """
    生成完整的 RAG context
    """
    context = ""
    
    # 1. 載入 trend.html 資料
    dashboard_info = extract_dashboard_data(TREND_HTML_PATH)
    if dashboard_info:
        context += format_trend_data(dashboard_info['trend_data'], dashboard_info['week_meta'])
        context += "\n"
        context += format_member_data(dashboard_info['member_data'])
        context += "\n"
        context += format_base_data(dashboard_info['base_data'])
        context += "\n"
    
    # 2. 載入各小區 JSON 資料
    district_data = load_district_json_data(DASHBOARD_BASE_DIR)
    if district_data:
        context += format_leaderboard_data(district_data)
        context += "\n"
        context += format_invite_data(district_data)
        context += "\n"
        context += format_recoverable_data(district_data)
        context += "\n"
    
    # 3. 載入 weekly.html 點名追蹤資料
    weekly_html_path = os.path.join(DASHBOARD_BASE_DIR, 'weekly.html')
    if os.path.exists(weekly_html_path):
        weekly_data = extract_weekly_data(weekly_html_path)
        if weekly_data:
            context += format_weekly_data(weekly_data)
            context += "\n"
    
    # 4. 載入 HTML 檔案文字內容
    html_text = load_html_files_as_text(DASHBOARD_BASE_DIR)
    if html_text:
        context += html_text
        context += "\n"
    
    print(f"✅ RAG context 生成完成，總字數: {len(context)}")
    return context


# 全域快取
GLOBAL_RAG_CONTEXT = "數據初始化中，請稍候..."


def update_rag_context():
    """
    更新全域 RAG context
    """
    global GLOBAL_RAG_CONTEXT
    print("🔄 正在更新 RAG 知識庫...")
    try:
        GLOBAL_RAG_CONTEXT = generate_rag_context()
        print("✅ 知識庫更新完成")
    except Exception as e:
        print(f"❌ 知識庫更新失敗: {e}")


def generate_response(query: str) -> str:
    """
    根據查詢生成回應
    """
    if not model:
        return "❌ RAG 功能未啟用，請檢查 Gemini API Key 設定。"
    
    if GLOBAL_RAG_CONTEXT == "數據初始化中，請稍候...":
        update_rag_context()
    
    system_prompt = """
你是一個智慧的教會數據分析機器人（81人數助理）。你的目標是根據用戶的問題和下方提供的『81Y3-dashboard 數據』來生成精確、簡潔且有條理的答案。

資料包含：
- 📈 出席趨勢：每週各項活動（主日、小排、晨興、禱告）的人數趨勢（2025年12月 - 2026年4月）
- 👥 成員名單：各小區成員（含性別、年齡層、角色）
- 📊 基數資料：各區的登記人數
- 🏆 排行榜：出席積分排名
- 💌 邀請與恢復資料：可恢復成員、不穩定成員的詳細資料
- 🔙 可恢復成員詳細資料：長期缺席和不穩定出席成員的統計
- � 本週點名追蹤：各小區本週出席狀況、各排出席人數、未出席成員名單（含配搭和歷史出席率）
- �📄 HTML 頁面內容：各主要頁面的文字說明和使用指南

回答原則：
1. 根據問題從資料中提取相關資訊
2. 數據不夠時，誠實告知並建議可用的查詢方向
3. 回答要簡潔、有條理，使用適當的符號和格式
4. 可以根據資料提供洞察和建議
5. 對於趨勢分析，要指出變化和模式
6. 對於恢復資料，可以建議關懷對象和優先順序
7. 可以從 HTML 頁面內容中提取系統使用說明和操作指南
8. 對於點名追蹤問題，可以查詢具體未出席成員名單及其配搭
"""

    full_prompt = f"{system_prompt}\n\n---\n\n{GLOBAL_RAG_CONTEXT}\n\n---\n\n用戶問題：{query}"
    
    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"❌ RAG 處理失敗: {e}"


if __name__ == "__main__":
    # 測試
    update_rag_context()
    # print("\n" + "="*80)
    # print("測試查詢：青年一區在3月參加主日聚會的有多少人？")
    # print("="*80)
    print(generate_response("甘順基目前的分數為何？"))
