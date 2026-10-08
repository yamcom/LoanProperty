const KEY = "loanproperty-mutual-aid-groups-v4";

class Group {
  constructor(id, period = 0, won = []) {
    this.id = id;
    this.period = Math.max(0, Math.min(25, +period || 0));
    this.slots = [];
    won = (won || []).map(Number);
    for (let i = 0; i < 5; i++) {
      this.slots.push(
        i < won.length
          ? { status: "won", paid: 15000 + Math.max(0, won[i] - 1) * 9000, won: won[i] }
          : { status: "active", paid: 15000 + this.period * 9000, won: null }
      );
    }
  }

  get active() {
    return this.slots.filter(s => s.status === "active").length;
  }

  get retired() {
    return this.active === 0 || this.period >= 25;
  }

  step(mode, rnd) {
    if (this.retired) return { pay: 0, payout: 0, interest: 0, invested: 0 };
    this.period++;
    let t = this.period,
      u = this.active,
      win = u && (mode === "worst" ? t >= 21 : rnd() < u / (26 - t)),
      payout = 0;

    if (win) {
      let s = this.slots.find(x => x.status === "active");
      s.status = "won";
      s.won = t;
      payout = t >= 25 ? 250000 : 10000 * t + 240 * (25 - t);
    }

    let a = this.slots.filter(s => s.status === "active");
    a.forEach(s => (s.paid += 9000));
    return {
      pay: a.length * 9000,
      payout,
      interest: a.reduce((x, s) => x + s.paid * 0.001, 0),
      invested: a.reduce((x, s) => x + s.paid, 0)
    };
  }
}

function fmt(n) {
  return "$" + Math.round(n).toLocaleString("zh-TW");
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function read() {
  return [...document.querySelectorAll("#groups tr")]
    .map(r => ({
      group_id: r.querySelector(".gid").value.trim(),
      current_period: +r.querySelector(".period").value || 0,
      won_periods: r
        .querySelector(".won")
        .value.split(",")
        .map(x => +x.trim())
        .filter(Number.isFinite)
    }))
    .filter(x => x.group_id);
}

function save() {
  localStorage.setItem(KEY, JSON.stringify(read()));
}

function add(d = { group_id: "", current_period: 0, won_periods: [] }) {
  let r = document.createElement("tr");
  r.innerHTML = `
    <td class="sn" style="text-align:center; font-weight:bold; color:#64748b;"></td>
    <td><input class="cell-input gid" value="${esc(d.group_id)}" placeholder="例: 25680613"></td>
    <td><input class="cell-input period" type="number" min="0" max="25" value="${d.current_period || 0}"></td>
    <td><input class="cell-input won" value="${esc((d.won_periods || []).join(", "))}" placeholder="例: 1, 3"></td>
    <td style="text-align:center;"><button class="secondary" style="color:var(--red); padding:4px 8px; margin:0;" onclick="this.closest('tr').remove();renum();save();simulate()">刪除</button></td>
  `;
  document.querySelector("#groups").appendChild(r);
  renum();
  save();
}

function renum() {
  document.querySelectorAll("#groups tr").forEach((r, i) => (r.querySelector(".sn").textContent = i + 1));
}

function simulate() {
  save();
  let capital = +document.querySelector("#capital").value || 0,
    target = +document.querySelector("#target_groups").value || 1,
    months = +document.querySelector("#total_months").value || 1,
    safe = +document.querySelector("#safe_months").value || 1,
    mode = document.querySelector("#sim_mode").value,
    auto = document.querySelector("#auto_replenish").checked,
    groups = read().map(x => new Group(x.group_id, x.current_period, x.won_periods)),
    past = groups.reduce((a, g) => a + g.slots.reduce((x, s) => x + s.paid, 0), 0),
    payout = groups.reduce(
      (a, g) =>
        a +
        g.slots
          .filter(s => s.status === "won")
          .reduce((x, s) => x + (s.won >= 25 ? 250000 : 10000 * s.won + 240 * (25 - s.won)), 0),
      0
    ),
    n = groups.length + 1;

  while (groups.length < target) {
    groups.push(new Group("NEW_" + String(n++).padStart(2, "0")));
    past += 75000;
  }

  let cash = capital - past + payout,
    seed = 42,
    rnd = () => {
      seed ^= seed << 13;
      seed ^= seed >>> 17;
      seed ^= seed << 5;
      return (seed >>> 0) / 4294967296;
    },
    rec = [
      {
        m: 0,
        g: groups.length,
        a: groups.reduce((x, g) => x + g.active, 0),
        pay: 0,
        payout: 0,
        interest: 0,
        invested: groups.reduce((x, g) => x + g.slots.filter(s => s.status === "active").reduce((z, s) => z + s.paid, 0), 0),
        cash,
        note: "起點"
      }
    ];

  for (let m = 1; m <= months; m++) {
    let pay = 0,
      po = 0,
      interest = 0,
      invested = 0;
    for (let g of groups.filter(g => !g.retired)) {
      let x = g.step(mode, rnd);
      pay += x.pay;
      po += x.payout;
      interest += x.interest;
      invested += x.invested;
    }
    cash += -pay + po + interest;
    let live = groups.filter(g => !g.retired),
      need = target - live.length,
      note = "正常運作";

    if (auto && need > 0) {
      let cushion = live.reduce((x, g) => x + g.active, 0) * 9000 * safe;
      for (let i = 0; i < need; i++) {
        if (cash >= 75000 + cushion) {
          groups.push(new Group("REP_" + String(n++).padStart(2, "0")));
          cash -= 75000;
          invested += 75000;
        } else {
          note = "現金未達安全氣墊，暫緩遞補";
          break;
        }
      }
    } else if (!auto && need > 0) {
      note = `已退場 ${need} 組 (自然結束模式)`;
    }

    rec.push({
      m,
      g: groups.filter(g => !g.retired).length,
      a: groups.reduce((x, g) => x + g.active, 0),
      pay,
      payout: po,
      interest,
      invested,
      cash,
      note
    });
  }
  render(rec);
}

function render(r) {
  let min = Math.min(...r.map(x => x.cash));
  document.querySelector("#start_cash").textContent = fmt(r[0].cash);
  document.querySelector("#min_cash").textContent = fmt(min);
  let d = document.querySelector("#debt");
  d.textContent = min < 0 ? "⚠️ 曾落入負債" : "✅ 全程未落入負債";
  d.style.color = min < 0 ? "var(--red)" : "var(--green)";

  document.querySelector("#records").innerHTML = r
    .map(
      x => `<tr>
        <td>${x.m ? "M" + x.m : "起點"}</td>
        <td>${x.g}</td>
        <td>${x.a}</td>
        <td>${fmt(x.pay)}</td>
        <td style="color:${x.payout > 0 ? "var(--green)" : "inherit"}; font-weight:${x.payout > 0 ? "bold" : "normal"};">${fmt(x.payout)}</td>
        <td style="color:var(--blue);">${fmt(x.interest)}</td>
        <td>${fmt(x.invested)}</td>
        <td style="font-weight:bold; color:${x.cash < 0 ? "var(--red)" : "inherit"};">${fmt(x.cash)}</td>
        <td style="text-align:left;">${esc(x.note)}</td>
      </tr>`
    )
    .join("");

  draw(r);
}

function draw(r) {
  const canvas = document.querySelector("#chart");
  const interestCanvas = document.querySelector("#interestChart");
  if (!canvas || !interestCanvas) return;

  // Chart.js 異步載入等待與重試機制
  if (typeof window.Chart === "undefined") {
    if (!window._chartRetry) window._chartRetry = 0;
    if (window._chartRetry < 30) {
      window._chartRetry++;
      setTimeout(() => draw(r), 100);
      return;
    }
    console.error("無法載入 Chart.js");
    return;
  }

  const labels = r.map(x => (x.m === 0 ? "起點" : "M" + x.m));
  const cashData = r.map(x => x.cash);
  const investedData = r.map(x => x.invested);
  const totalData = r.map(x => x.cash + x.invested); // 計算總資金：剩餘未投入資金 + 在會累積本金
  const interestData = r.map(x => x.interest);

  // 安全銷毀既有實例
  if (window.cashChart && typeof window.cashChart.destroy === "function") {
    window.cashChart.destroy();
  }
  if (window.interestChart && typeof window.interestChart.destroy === "function") {
    window.interestChart.destroy();
  }

  const moneyTick = v => "$" + Number(v).toLocaleString("zh-TW");

  // 1. 折線圖：總資金(紅)、未投入資金(藍)、在會本金(綠)
  window.cashChart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "總資金 (未投入現金 + 在會本金)",
          data: totalData,
          borderColor: "#dc2626", // 紅色
          backgroundColor: "transparent",
          borderWidth: 2.8,
          pointRadius: 2.5,
          pointHoverRadius: 5,
          fill: false,
          tension: 0.2
        },
        {
          label: "剩餘未投入資金 (流動現金水位)",
          data: cashData,
          borderColor: "#2563eb", // 藍色
          backgroundColor: "rgba(37,99,235,0.07)",
          borderWidth: 2.5,
          pointRadius: 2.5,
          pointHoverRadius: 5,
          fill: true,
          tension: 0.2
        },
        {
          label: "在會累積本金資產",
          data: investedData,
          borderColor: "#16a34a", // 綠色
          borderWidth: 2.5,
          borderDash: [5, 5],
          pointRadius: 2.5,
          pointHoverRadius: 5,
          fill: false,
          tension: 0.2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { color: "rgba(148,163,184,0.18)" },
          ticks: { maxRotation: 0, minRotation: 0 }
        },
        y: {
          title: { display: true, text: "金額 (TWD)" },
          grid: { color: "rgba(148,163,184,0.18)" },
          ticks: { callback: moneyTick }
        }
      },
      plugins: {
        legend: { display: true, position: "top" },
        tooltip: {
          callbacks: {
            label: c => c.dataset.label + ": " + moneyTick(Math.round(c.parsed.y))
          }
        }
      }
    }
  });

  // 2. 長條圖：每月配息
  window.interestChart = new Chart(interestCanvas.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "每月 0.1% 活會配息收入",
          data: interestData,
          backgroundColor: "rgba(245,158,11,0.72)",
          borderColor: "#d97706",
          borderWidth: 1,
          borderRadius: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          grid: { color: "rgba(148,163,184,0.18)" },
          ticks: { maxRotation: 0, minRotation: 0 }
        },
        y: {
          beginAtZero: true,
          title: { display: true, text: "配息金額 (元)" },
          grid: { color: "rgba(148,163,184,0.18)" },
          ticks: { callback: moneyTick }
        }
      },
      plugins: {
        legend: { display: true, position: "top" },
        tooltip: {
          callbacks: {
            label: c => "每月配息: " + moneyTick(Math.round(c.parsed.y))
          }
        }
      }
    }
  });
}

// 按鈕事件綁定
document.querySelector("#add").onclick = () => add();
document.querySelector("#run").onclick = simulate;

// 匯出 JSON
document.querySelector("#export").onclick = () => {
  let data = read();
  if (data.length === 0) {
    alert("目前清單為空，請先新增會組！");
    return;
  }
  let b = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
    u = URL.createObjectURL(b),
    a = document.createElement("a");
  a.href = u;
  a.download = "mutual_aid_groups.json";
  a.click();
  URL.revokeObjectURL(u);
};

// 匯入 JSON
document.querySelector("#import").onchange = e => {
  let f = e.target.files[0];
  if (!f) return;
  let r = new FileReader();
  r.onload = () => {
    try {
      let list = JSON.parse(r.result);
      if (!Array.isArray(list)) throw new Error();
      document.querySelector("#groups").innerHTML = "";
      list.forEach(add);
      simulate();
    } catch {
      alert("JSON 檔案格式錯誤！");
    }
  };
  r.readAsText(f);
  e.target.value = "";
};

// 初始化載入
try {
  let saved = JSON.parse(localStorage.getItem(KEY) || "[]");
  saved.forEach(add);
} catch {}

// DOM 加載完成後自動執行首次模擬
window.addEventListener("DOMContentLoaded", () => {
  simulate();
});