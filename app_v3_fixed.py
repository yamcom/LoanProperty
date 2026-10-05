import json
import random
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==================== 獨立會組物件模型 ====================
class V3MutualAidGroup:
    def __init__(self, group_id, start_date="2026.05.25", current_period=0, won_periods=None):
        self.group_id = group_id
        self.start_date = start_date
        self.group_period = current_period  # 該組目前已進行之期數 (0~25)
        self.slots = []
        
        won_periods = won_periods or []
        won_count = len(won_periods)
        
        # 建立旗下 5 個會號狀態
        for i in range(5):
            if i < won_count:
                wp = won_periods[i]
                # 歷史得標會號累計已繳：首期15,000 + (wp-1)*9,000
                paid = 15000.0 + max(0, wp - 1) * 9000.0
                self.slots.append({'id': i + 1, 'status': 'won', 'paid': paid, 'won_period': wp})
            else:
                # 歷史未得標活會累計已繳：首期15,000 + (current_period)*9,000
                paid = 15000.0 + max(0, current_period) * 9000.0
                self.slots.append({'id': i + 1, 'status': 'active', 'paid': paid, 'won_period': None})
                
        self.is_retired = (self.active_slots_count == 0 or self.group_period >= 25)

    @property
    def active_slots_count(self):
        return sum(1 for s in self.slots if s['status'] == 'active')

    def step_month(self, mode="normal"):
        if self.is_retired or self.group_period >= 25:
            self.is_retired = True
            return {'payment': 0.0, 'payout': 0.0, 'interest': 0.0, 'invested': 0.0}

        self.group_period += 1
        t = self.group_period
        u = self.active_slots_count
        total_in_group = 26 - t  # 全組剩餘總人數
        
        user_won = False
        if u > 0:
            if mode == "worst":
                # 最差狀況：若到了第21~25期，自己強制得標
                if t >= 21:
                    user_won = True
            else:
                # 常態獨立抽籤機率：u / (26 - t)
                prob = u / total_in_group
                if random.random() < prob:
                    user_won = True

        payout = 0.0
        if user_won:
            active_slots = [s for s in self.slots if s['status'] == 'active']
            target = active_slots[0]
            target['status'] = 'won'
            target['won_period'] = t
            payout = 250000.0 if t >= 25 else (10000.0 * t + 240.0 * (25 - t))

        # 剩餘活會每會繳納 9,000 元標金
        rem_active = [s for s in self.slots if s['status'] == 'active']
        payment = len(rem_active) * 9000.0
        for s in rem_active:
            s['paid'] += 9000.0

        # 活會月息 0.1% 配息
        interest = sum(s['paid'] * 0.001 for s in rem_active)
        invested = sum(s['paid'] for s in rem_active)

        if len(rem_active) == 0 or t >= 25:
            self.is_retired = True

        return {
            'payment': payment,
            'payout': payout,
            'interest': interest,
            'invested': invested
        }

# ==================== 模擬試算引擎 ====================
def run_simulation_v3(capital, target_groups, total_months, safe_months, auto_replenish, sim_mode, existing_groups_data):
    random.seed(42)
    groups = []
    group_counter = 1

    # 1. 載入使用者輸入之已投入會組清單
    total_past_paid = 0.0
    total_past_payout = 0.0
    
    for eg in existing_groups_data:
        gid = str(eg.get('group_id', f'G{group_counter:02d}'))
        sdate = str(eg.get('start_date', '2026.05.25'))
        c_period = int(eg.get('current_period', 0))
        won_periods = [int(p) for p in eg.get('won_periods', []) if str(p).strip().isdigit()]
        
        g = V3MutualAidGroup(gid, sdate, c_period, won_periods)
        groups.append(g)
        group_counter += 1
        
        # 統計過去已實繳與得標領回
        for s in g.slots:
            total_past_paid += s['paid']
            if s['status'] == 'won':
                wp = s['won_period']
                payout = 250000.0 if wp >= 25 else (10000.0 * wp + 240.0 * (25 - wp))
                total_past_payout += payout

    # 2. 若維持組數高於已輸入組數，自動補充全新組別
    needed_initial = max(0, target_groups - len(groups))
    for _ in range(needed_initial):
        g = V3MutualAidGroup(group_id=f"NEW_{group_counter:02d}", start_date="2026.10.15", current_period=0, won_periods=[])
        groups.append(g)
        group_counter += 1
        total_past_paid += 5 * 15000.0  # 全新組第0期預繳

    # 初始可動用現金結餘 = 原始資金總額 - 歷史與全新組已付 + 歷史已得標領回
    uninvested_cash = float(capital) - total_past_paid + total_past_payout

    records = []
    live_groups = [g for g in groups if not g.is_retired]
    init_active_slots = sum(g.active_slots_count for g in live_groups)
    init_invested = sum(sum(s['paid'] for s in g.slots if s['status'] == 'active') for g in live_groups)

    records.append({
        'month': 0,
        'date_desc': '目前起點現況',
        'active_groups': len(live_groups),
        'total_active_slots': init_active_slots,
        'total_won_slots': (len(groups) * 5) - init_active_slots,
        'monthly_payment': 0.0,
        'monthly_payout': 0.0,
        'monthly_interest': 0.0,
        'uninvested_cash': round(uninvested_cash, 2),
        'invested_capital': round(init_invested, 2),
        'new_groups_added': needed_initial,
        'status_note': f'已載入 {len(existing_groups_data)} 現有組，系統補齊 {needed_initial} 組全新組'
    })

    # 開始向未來各月推進
    for m in range(1, total_months + 1):
        live_groups = [g for g in groups if not g.is_retired]
        if not live_groups:
            records.append({
                'month': m,
                'date_desc': f'未來第 {m} 個月 (15日)',
                'active_groups': 0,
                'total_active_slots': 0,
                'total_won_slots': len(groups) * 5,
                'monthly_payment': 0.0,
                'monthly_payout': 0.0,
                'monthly_interest': 0.0,
                'uninvested_cash': round(uninvested_cash, 2),
                'invested_capital': 0.0,
                'new_groups_added': 0,
                'status_note': '所有會組均已在第 25 期前全數得標結清'
            })
            continue

        m_payment = 0.0
        m_payout = 0.0
        m_interest = 0.0
        m_invested = 0.0

        for g in live_groups:
            res = g.step_month(mode=sim_mode)
            m_payment += res['payment']
            m_payout += res['payout']
            m_interest += res['interest']
            m_invested += res['invested']

        uninvested_cash = uninvested_cash - m_payment + m_payout + m_interest

        active_after = [g for g in groups if not g.is_retired]
        needed_groups = target_groups - len(active_after)
        new_added = 0
        note = "各組獨立抽籤扣繳運作中"

        if auto_replenish and needed_groups > 0:
            current_active_slots = sum(g.active_slots_count for g in active_after)
            required_safety_cushion = current_active_slots * 9000.0 * safe_months
            for _ in range(needed_groups):
                single_cost = 5 * 15000.0  # 75,000 元
                if uninvested_cash >= (single_cost + required_safety_cushion):
                    new_g = V3MutualAidGroup(group_id=f"REP_{group_counter:02d}", start_date=f"M{m}", current_period=0, won_periods=[])
                    groups.append(new_g)
                    group_counter += 1
                    uninvested_cash -= single_cost
                    m_invested += single_cost
                    new_added += 1
                else:
                    note = f"缺額 {needed_groups} 組，現金未達安全防禦門檻 ({int(required_safety_cushion):,}元)，暫緩遞補防負債"
                    break
            if new_added > 0:
                note = f"通過安全門檻，成功動態遞補 {new_added} 組新會組 (維持組數)"
        elif not auto_replenish and needed_groups > 0:
            note = f"累計已退場 {len(groups) - len(active_after)} 組（自然結束模式：不遞補）"

        total_live_slots = sum(g.active_slots_count for g in groups if not g.is_retired)
        total_won = len(groups) * 5 - total_live_slots

        records.append({
            'month': m,
            'date_desc': f'未來第 {m} 個月 (15日)',
            'active_groups': len(active_after),
            'total_active_slots': total_live_slots,
            'total_won_slots': total_won,
            'monthly_payment': round(m_payment, 2),
            'monthly_payout': round(m_payout, 2),
            'monthly_interest': round(m_interest, 2),
            'uninvested_cash': round(uninvested_cash, 2),
            'invested_capital': round(m_invested, 2),
            'new_groups_added': new_added,
            'status_note': note
        })

    return {
        'initial_capital': capital,
        'target_groups': target_groups,
        'records': records
    }

# ==================== 前端 HTML 介面 ====================
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>會務財產推估模擬系統 v3.1</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --success: #16a34a;
            --danger: #dc2626;
            --warning: #d97706;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #0f172a;
        }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }
        .container { max-width: 1320px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .card { background: var(--card); border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07); margin-bottom: 20px; }
        .grid-inputs { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; align-items: end; }
        label { font-size: 13px; font-weight: 600; color: #64748b; margin-bottom: 6px; display: block; }
        input, select { width: 100%; box-sizing: border-box; padding: 10px 14px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 15px; outline: none; background: #fff; }
        input:focus, select:focus { border-color: var(--primary); }
        
        .toggle-box { display: flex; align-items: center; justify-content: space-between; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 10px 14px; }
        .toggle-label { font-weight: 600; color: #1e40af; font-size: 13.5px; }
        .switch { position: relative; display: inline-block; width: 46px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e1; transition: .3s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .3s; border-radius: 50%; }
        input:checked + .slider { background-color: var(--primary); }
        input:checked + .slider:before { transform: translateX(22px); }

        .btn-run { background: var(--primary); color: #fff; border: none; padding: 12px 24px; border-radius: 8px; font-size: 15px; font-weight: 600; cursor: pointer; height: 44px; }
        .btn-run:hover { background: #1d4ed8; }
        .btn-secondary { background: #e2e8f0; color: #334155; border: none; padding: 8px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: 0.2s; }
        .btn-secondary:hover { background: #cbd5e1; }

        /* 黃色提示框樣式 */
        .info-card { background: #fefce8; border-left: 4px solid #eab308; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-top: 16px; font-size: 14px; line-height: 1.65; color: #713f12; }
        .info-card strong { color: #854d0e; }

        .summary-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-top: 16px; }
        .stat-box { background: #f1f5f9; border-radius: 8px; padding: 16px; }
        .stat-box .title { font-size: 12px; color: #64748b; font-weight: 600; }
        .stat-box .value { font-size: 20px; font-weight: 700; margin-top: 4px; }
        
        .chart-box { height: 380px; position: relative; }
        .table-responsive { overflow-x: auto; max-height: 480px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: right; }
        th, td { padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }
        th { background: #f8fafc; color: #475569; position: sticky; top: 0; z-index: 10; font-weight: 600; }
        td:first-child, th:first-child { text-align: left; }
        .badge { padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
        .badge-success { background: #dcfce7; color: var(--success); }
        .badge-warning { background: #fef3c7; color: var(--warning); }
        .badge-danger { background: #fee2e2; color: var(--danger); }

        /* 清單表格樣式 */
        .input-table td { padding: 8px 10px; text-align: center; }
        .input-table input { padding: 8px 10px; font-size: 13.5px; text-align: center; }
        .col-sn { font-weight: 700; color: #64748b; }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div>
            <h2 style="margin:0;">會務財產推估模擬系統 v3.1</h2>
            <small style="color:#64748b;">自訂現有會組清單 ｜ 自動補齊目標組數 ｜ 支援常態抽籤與最差後5期情境</small>
        </div>
        <button class="btn-run" onclick="runSimulation()">執行第 3 版模擬計算</button>
    </div>

    <!-- 核心參數面板 -->
    <div class="card">
        <div class="grid-inputs">
            <div>
                <label>原始資金總額 (TWD)</label>
                <input type="number" id="capital" value="3000000" step="100000">
            </div>
            <div>
                <label>目標維持組數 (每組5會)</label>
                <input type="number" id="target_groups" value="13" min="1" max="25">
            </div>
            <div>
                <label>模擬推估總月數</label>
                <input type="number" id="total_months" value="36" min="12" max="60">
            </div>
            <div>
                <label>防負債預備金月數 (安全氣墊)</label>
                <input type="number" id="safe_months" value="3" min="1" max="6">
            </div>
            <div>
                <label>抽籤模式模擬</label>
                <select id="sim_mode">
                    <option value="normal">常態獨立機率抽籤</option>
                    <option value="worst">最差狀況 (未得標會於21~25期得標)</option>
                </select>
            </div>
            <div>
                <label>遞補機制切換</label>
                <div class="toggle-box">
                    <span class="toggle-label" id="toggle_text">全組退場自然結束</span>
                    <label class="switch">
                        <input type="checkbox" id="auto_replenish" onchange="updateToggleText()">
                        <span class="slider"></span>
                    </label>
                </div>
            </div>
        </div>

        <!-- 嚴格規定的黃色說明提示框 -->
        <div class="info-card">
            💡 <strong>會組規則重要說明與防負債預備金用途：</strong><br>
            • <strong>25個月必然結束機制</strong>：每個會組由「您(5會)＋其他4人(20會)」組成，各組獨立運作。因他人僅有20會，最差狀況下第20期他人全數得標後，第21～25期您享有100%得標權，單一會組絕不可能超過25個月！<br>
            • <strong>防負債預備金用途</strong>：第13～15會期為現金流低谷，若剛好有組別退場，系統會強制檢驗：未投入現金 &ge; 75,000 + 現有活會 &times; 9,000 &times; 安全氣墊月數 。只有現金足以支應現有活會未來數月扣款時才准開新組，避免資金歸零落入負債。
        </div>

        <div class="summary-cards">
            <div class="stat-box">
                <div class="title">目前起點結餘現金</div>
                <div class="value" id="disp_start_cash" style="color:var(--primary);">$0</div>
            </div>
            <div class="stat-box">
                <div class="title">全期最低現金水位 (谷底)</div>
                <div class="value" id="disp_min_cash">$0</div>
            </div>
            <div class="stat-box">
                <div class="title">現金流負債狀態</div>
                <div class="value" id="disp_debt_status" style="color:var(--success);">無負債</div>
            </div>
            <div class="stat-box">
                <div class="title">活會配息機制</div>
                <div class="value" style="font-size:16px;">年息 1.2% (月息 0.1%)</div>
            </div>
        </div>
    </div>

    <!-- 已投入會組清單輸入區塊 -->
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <div>
                <h3 style="margin:0; font-size:15px; display:inline-block;">輸入現有會組清單</h3>
                <small style="color:#64748b; margin-left:8px;">(若組數未滿目標組數，系統自動補充全新會組)</small>
            </div>
            <div>
                <!-- 隱藏式檔案選取器 -->
                <input type="file" id="importFileInput" accept=".json" style="display:none;" onchange="handleFileImport(event)">
                <button class="btn-secondary" onclick="document.getElementById('importFileInput').click()">📂 載入會組清單</button>
                <button class="btn-secondary" onclick="exportGroupsToFile()" style="margin-left:6px;">💾 儲存目前清單</button>
                <button class="btn-secondary" onclick="addGroupRow()" style="margin-left:6px;">＋ 新增會組</button>
            </div>
        </div>
        <div class="table-responsive" style="max-height:300px;">
            <table class="input-table" id="groupInputTable">
                <thead>
                    <tr>
                        <th style="width:70px; text-align:center;">流水編號</th>
                        <th style="width:180px; text-align:center;">會組編號</th>
                        <th style="width:150px; text-align:center;">起始日期</th>
                        <th style="width:130px; text-align:center;">目前已進行期數</th>
                        <th style="width:200px; text-align:center;">已得標之會期 (逗號分隔)</th>
                        <th style="width:80px; text-align:center;">操作</th>
                    </tr>
                </thead>
                <tbody id="groupInputBody"></tbody>
            </table>
        </div>
    </div>

    <!-- 走勢圖 -->
    <div class="card">
        <h3 style="margin-top:0; font-size:15px;">現金流水位與在會資產走勢 (Chart.js)</h3>
        <div class="chart-box">
            <canvas id="mainChart"></canvas>
        </div>
    </div>

    <!-- 輸出明細表格 -->
    <div class="card">
        <h3 style="margin-top:0; font-size:15px;">未來每月 15 日收支、配息與遞補決策追蹤明細表</h3>
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>會期月份</th>
                        <th>有效組數 / 活會數</th>
                        <th>當期應繳</th>
                        <th>當期得標實領</th>
                        <th>本月配息(0.1%)</th>
                        <th>在會本金</th>
                        <th>剩餘未投入資金</th>
                        <th style="text-align:left;">狀態備註與會組動態</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>
    </div>
</div>

<script>
let chartInstance = null;

// 重新整理流水編號 (1, 2, 3...)
function refreshSerialNumbers() {
    const rows = document.querySelectorAll('#groupInputBody tr');
    rows.forEach((r, idx) => {
        r.querySelector('.col-sn').innerText = idx + 1;
    });
}

function addGroupRow(data = { gid: "", sdate: "2026.10.01", period: 0, won: "" }) {
    const tbody = document.getElementById('groupInputBody');
    const tr = document.createElement('tr');
    tr.innerHTML = `
        <td class="col-sn">1</td>
        <td><input type="text" class="in-gid" value="${data.gid}" placeholder="例: G01"></td>
        <td><input type="text" class="in-sdate" value="${data.sdate}"></td>
        <td><input type="number" class="in-period" value="${data.period}" min="0" max="25"></td>
        <td><input type="text" class="in-won" value="${data.won}" placeholder="例: 1, 3"></td>
        <td><button class="btn-secondary" style="color:var(--danger); padding:4px 8px;" onclick="removeGroupRow(this)">刪除</button></td>
    `;
    tbody.appendChild(tr);
    refreshSerialNumbers();
}

function removeGroupRow(btn) {
    btn.closest('tr').remove();
    refreshSerialNumbers();
}

// 取得畫面目前輸入的會組資料
function getExistingGroupsData() {
    const rows = document.querySelectorAll('#groupInputBody tr');
    const result = [];
    rows.forEach(r => {
        const gid = r.querySelector('.in-gid').value.trim();
        const sdate = r.querySelector('.in-sdate').value.trim();
        const period = parseInt(r.querySelector('.in-period').value) || 0;
        const wonStr = r.querySelector('.in-won').value.trim();
        const won_periods = wonStr ? wonStr.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n)) : [];
        if (gid) {
            result.push({ group_id: gid, start_date: sdate, current_period: period, won_periods: won_periods });
        }
    });
    return result;
}

// 儲存目前清單為 JSON 檔案
function exportGroupsToFile() {
    const list = getExistingGroupsData();
    if (list.length === 0) {
        alert('目前會組清單為空，請先新增資料後再儲存！');
        return;
    }
    const jsonStr = JSON.stringify(list, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mutual_aid_groups.json';
    a.click();
    URL.revokeObjectURL(url);
}

// 載入會組清單 JSON 檔案
function handleFileImport(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const data = JSON.parse(e.target.result);
            if (!Array.isArray(data)) {
                alert('檔案格式錯誤：內容必須是會組陣列清單！');
                return;
            }
            const tbody = document.getElementById('groupInputBody');
            tbody.innerHTML = '';
            data.forEach(item => {
                const wonStr = Array.isArray(item.won_periods) ? item.won_periods.join(', ') : (item.won || '');
                addGroupRow({
                    gid: item.group_id || item.gid || '',
                    sdate: item.start_date || item.sdate || '2026.05.25',
                    period: item.current_period !== undefined ? item.current_period : (item.period || 0),
                    won: wonStr
                });
            });
            refreshSerialNumbers();
            runSimulation();
        } catch (err) {
            alert('無法解析檔案，請確認為正確的 JSON 格式！');
        }
    };
    reader.readAsText(file);
    // 重設選取器以便重複載入同檔名
    event.target.value = '';
}

function updateToggleText() {
    const isChecked = document.getElementById('auto_replenish').checked;
    const txt = document.getElementById('toggle_text');
    txt.innerText = isChecked ? "自動遞補維持組數" : "全組退場自然結束";
}

async function runSimulation() {
    const capital = document.getElementById('capital').value;
    const targetGroups = document.getElementById('target_groups').value;
    const totalMonths = document.getElementById('total_months').value;
    const safeMonths = document.getElementById('safe_months').value;
    const simMode = document.getElementById('sim_mode').value;
    const autoReplenish = document.getElementById('auto_replenish').checked;

    updateToggleText();
    const existingGroups = getExistingGroupsData();

    const payload = {
        capital: parseFloat(capital),
        target_groups: parseInt(targetGroups),
        total_months: parseInt(totalMonths),
        safe_months: parseInt(safeMonths),
        auto_replenish: autoReplenish,
        sim_mode: simMode,
        existing_groups: existingGroups
    };

    const res = await fetch('/api/simulate_v3', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    const data = await res.json();
    
    renderTable(data.records);
    renderChart(data.records);
    updateStats(data.records);
}

function updateStats(records) {
    let minCash = Infinity;
    let hasDebt = false;

    records.forEach(r => {
        if (r.uninvested_cash < minCash) minCash = r.uninvested_cash;
        if (r.uninvested_cash < 0) hasDebt = true;
    });

    document.getElementById('disp_start_cash').innerText = "$" + Math.round(records[0].uninvested_cash).toLocaleString();
    document.getElementById('disp_min_cash').innerText = "$" + Math.round(minCash).toLocaleString();
    const debtElem = document.getElementById('disp_debt_status');
    if (hasDebt) {
        debtElem.innerText = "⚠️ 警訊：曾落入現金負債！";
        debtElem.style.color = "var(--danger)";
    } else {
        debtElem.innerText = "✅ 安全：全程未投入資金維持正值";
        debtElem.style.color = "var(--success)";
    }
}

function renderTable(records) {
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';

    records.forEach(r => {
        const tr = document.createElement('tr');
        const isNegative = r.uninvested_cash < 0;
        let badgeClass = 'badge-success';
        if (r.new_groups_added > 0) badgeClass = 'badge-warning';
        if (isNegative) badgeClass = 'badge-danger';

        tr.innerHTML = `
            <td><strong>${r.date_desc}</strong></td>
            <td><span class="badge ${badgeClass}">${r.active_groups} 組 / ${r.total_active_slots} 活會</span></td>
            <td>$${r.monthly_payment.toLocaleString()}</td>
            <td style="color:${r.monthly_payout > 0 ? '#16a34a' : 'inherit'}; font-weight:${r.monthly_payout > 0 ? '700' : 'normal'}">
                $${r.monthly_payout.toLocaleString()}
            </td>
            <td style="color:#2563eb;">+$${r.monthly_interest.toLocaleString()}</td>
            <td>$${r.invested_capital.toLocaleString()}</td>
            <td style="font-weight:700; color:${isNegative ? '#dc2626' : '#0f172a'}">
                $${r.uninvested_cash.toLocaleString()}
            </td>
            <td style="text-align:left; font-size:12px; color:#475569;">${r.status_note}</td>
        `;
        tbody.appendChild(tr);
    });
}

function renderChart(records) {
    const labels = records.map(r => r.month === 0 ? '起點' : 'M' + r.month);
    const cashData = records.map(r => r.uninvested_cash);
    const investedData = records.map(r => r.invested_capital);

    if (chartInstance) chartInstance.destroy();

    const ctx = document.getElementById('mainChart').getContext('2d');
    chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '剩餘未投入資金 (流動現金水位)',
                    data: cashData,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,0.07)',
                    fill: true,
                    tension: 0.2
                },
                {
                    label: '在會累積本金資產',
                    data: investedData,
                    borderColor: '#16a34a',
                    borderDash: [5, 5],
                    fill: false,
                    tension: 0.2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    title: { display: true, text: '金額 (TWD)' },
                    ticks: { callback: v => '$' + v.toLocaleString() }
                }
            }
        }
    });
}

// 頁面初次載入：清單預設為空白，執行純全新組模擬
window.onload = () => {
    runSimulation();
};
</script>
</body>
</html>
"""

# ==================== 伺服器 Handler ====================
class SimServerHandlerV3(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ['/', '/index.html']:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/simulate_v3':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode('utf-8'))

            capital = float(data.get('capital', 3000000))
            target_groups = int(data.get('target_groups', 13))
            total_months = int(data.get('total_months', 36))
            safe_months = int(data.get('safe_months', 3))
            auto_replenish = bool(data.get('auto_replenish', False))
            sim_mode = str(data.get('sim_mode', 'normal'))
            existing_groups = data.get('existing_groups', [])

            result = run_simulation_v3(capital, target_groups, total_months, safe_months, auto_replenish, sim_mode, existing_groups)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=8888):
    server_address = ('', port)
    httpd = HTTPServer(server_address, SimServerHandlerV3)
    print("==================================================")
    print(f"  會務財產推估模擬系統 v3.1 服務已啟動！")
    print(f"  瀏覽器開啟: http://localhost:{port}")
    print(f"  API 端點: POST http://localhost:{port}/api/simulate_v3")
    print("==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已正常停止。")

if __name__ == '__main__':
    run_server(8888)