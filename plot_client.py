import json
import urllib.request
import matplotlib.pyplot as plt

# 1. 向運行中的 8888 port 請求最新模擬數據
url = "http://localhost:8888/api/simulate?capital=3000000&groups=13"
response = urllib.request.urlopen(url)
data = json.loads(response.read().decode('utf-8'))

records = data['records']
months = [r['month'] for r in records]
cash = [r['uninvested_cash'] for r in records]
invested = [r['invested_capital'] for r in records]
interest = [r['monthly_interest'] for r in records]

# 2. 使用 Matplotlib 繪製雙子圖
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)

# 資金水位與在會資產
ax1.plot(months, cash, marker='o', color='#2563eb', label='剩餘未投入現金水位')
ax1.plot(months, invested, marker='s', linestyle='--', color='#16a34a', label='在會本金資產')
ax1.axhline(0, color='red', linewidth=1, linestyle=':')
ax1.set_ylabel('金額 (新台幣元)')
ax1.set_title('會務資產與現金流動態模擬 (13組 / 25期)')
ax1.legend()
ax1.grid(True, alpha=0.3)

# 每月利息配息收入
ax2.bar(months, interest, color='#f59e0b', width=0.6, label='每月0.1%活會配息收入')
ax2.set_xlabel('會期進度 (月份)')
ax2.set_ylabel('配息金額 (元)')
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('simulation_chart.png', dpi=300)
print("圖表已成功輸出為 simulation_chart.png！")