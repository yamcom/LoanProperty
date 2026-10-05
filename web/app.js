const KEY="loanproperty-mutual-aid-groups-v4";class Group{constructor(id,period=0,won=[]){this.id=id;this.period=Math.max(0,Math.min(25,+period||0));this.slots=[];won=(won||[]).map(Number);for(let i=0;i<5;i++)this.slots.push(i<won.length?{status:"won",paid:15000+Math.max(0,won[i]-1)*9000,won:won[i]}:{status:"active",paid:15000+this.period*9000,won:null})}get active(){return this.slots.filter(s=>s.status==="active").length}get retired(){return this.active===0||this.period>=25}step(mode,rnd){if(this.retired)return{pay:0,payout:0,interest:0,invested:0};this.period++;let t=this.period,u=this.active,win=u&&(mode==="worst"?t>=21:rnd()<u/(26-t)),payout=0;if(win){let s=this.slots.find(x=>x.status==="active");s.status="won";s.won=t;payout=t>=25?250000:10000*t+240*(25-t)}let a=this.slots.filter(s=>s.status==="active");a.forEach(s=>s.paid+=9000);return{pay:a.length*9000,payout,interest:a.reduce((x,s)=>x+s.paid*.001,0),invested:a.reduce((x,s)=>x+s.paid,0)}}}function fmt(n){return"$"+Math.round(n).toLocaleString("zh-TW")}function esc(s){return String(s??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;")}function read(){return[...document.querySelectorAll("#groups tr")].map(r=>({group_id:r.querySelector(".gid").value.trim(),current_period:+r.querySelector(".period").value||0,won_periods:r.querySelector(".won").value.split(",").map(x=>+x.trim()).filter(Number.isFinite)})).filter(x=>x.group_id)}function save(){localStorage.setItem(KEY,JSON.stringify(read()))}function add(d={group_id:"",current_period:0,won_periods:[]}){let r=document.createElement("tr");r.innerHTML=`<td class="sn"></td><td><input class="cell-input gid" value="${esc(d.group_id)}"></td><td><input class="cell-input period" type="number" min="0" max="25" value="${d.current_period||0}"></td><td><input class="cell-input won" value="${esc((d.won_periods||[]).join(", "))}" placeholder="1, 3"></td><td><button class="secondary" onclick="this.closest('tr').remove();renum();save();simulate()">刪除</button></td>`;document.querySelector("#groups").appendChild(r);renum();save()}function renum(){document.querySelectorAll("#groups tr").forEach((r,i)=>r.querySelector(".sn").textContent=i+1)}function simulate(){save();let capital=+document.querySelector("#capital").value||0,target=+document.querySelector("#target_groups").value||1,months=+document.querySelector("#total_months").value||1,safe=+document.querySelector("#safe_months").value||1,mode=document.querySelector("#sim_mode").value,auto=document.querySelector("#auto_replenish").checked,groups=read().map(x=>new Group(x.group_id,x.current_period,x.won_periods)),past=groups.reduce((a,g)=>a+g.slots.reduce((x,s)=>x+s.paid,0),0),payout=groups.reduce((a,g)=>a+g.slots.filter(s=>s.status==="won").reduce((x,s)=>x+(s.won>=25?250000:10000*s.won+240*(25-s.won)),0),0),n=groups.length+1;while(groups.length<target){groups.push(new Group("NEW_"+String(n++).padStart(2,"0")));past+=75000}let cash=capital-past+payout,seed=42,rnd=()=>{seed^=seed<<13;seed^=seed>>>17;seed^=seed<<5;return(seed>>>0)/4294967296},rec=[{m:0,g:groups.length,a:groups.reduce((x,g)=>x+g.active,0),pay:0,payout:0,interest:0,invested:groups.reduce((x,g)=>x+g.slots.filter(s=>s.status==="active").reduce((z,s)=>z+s.paid,0),0),cash,note:"起點"}];for(let m=1;m<=months;m++){let pay=0,po=0,interest=0,invested=0;for(let g of groups.filter(g=>!g.retired)){let x=g.step(mode,rnd);pay+=x.pay;po+=x.payout;interest+=x.interest;invested+=x.invested}cash+=-pay+po+interest;let live=groups.filter(g=>!g.retired),need=target-live.length,note="正常運作";if(auto&&need>0){let cushion=live.reduce((x,g)=>x+g.active,0)*9000*safe;for(let i=0;i<need;i++){if(cash>=75000+cushion){groups.push(new Group("REP_"+String(n++).padStart(2,"0")));cash-=75000;invested+=75000}else{note="現金不足，暫緩遞補";break}}}rec.push({m,g:groups.filter(g=>!g.retired).length,a:groups.reduce((x,g)=>x+g.active,0),pay,payout:po,interest,invested,cash,note})}render(rec)}function render(r){let min=Math.min(...r.map(x=>x.cash));document.querySelector("#start_cash").textContent=fmt(r[0].cash);document.querySelector("#min_cash").textContent=fmt(min);let d=document.querySelector("#debt");d.textContent=min<0?"⚠️ 曾落入負債":"✅ 全程未落入負債";d.style.color=min<0?"var(--red)":"var(--green)";document.querySelector("#records").innerHTML=r.map(x=>`<tr><td>${x.m?"M"+x.m:"起點"}</td><td>${x.g}</td><td>${x.a}</td><td>${fmt(x.pay)}</td><td>${fmt(x.payout)}</td><td>${fmt(x.interest)}</td><td>${fmt(x.invested)}</td><td>${fmt(x.cash)}</td><td>${esc(x.note)}</td></tr>`).join("");draw(r)}function draw(r){
  const canvas=document.querySelector("#chart");
  if(!canvas)return;
  if(!window.Chart){
    const ctx=canvas.getContext("2d");
    ctx.clearRect(0,0,canvas.width,canvas.height);
    return;
  }

  const labels=r.map(x=>x.m===0?"起點":"M"+x.m);
  const cashData=r.map(x=>x.cash);
  const investedData=r.map(x=>x.invested);

  if(window.chartInstance) window.chartInstance.destroy();

  const ctx=canvas.getContext("2d");
  window.chartInstance=new Chart(ctx,{
    type:"line",
    data:{
      labels,
      datasets:[
        {
          label:"剩餘未投入資金 (流動現金水位)",
          data:cashData,
          borderColor:"#2563eb",
          backgroundColor:"rgba(37,99,235,0.07)",
          borderWidth:2.5,
          pointRadius:3,
          pointHoverRadius:5,
          fill:true,
          tension:0.2
        },
        {
          label:"在會累積本金資產",
          data:investedData,
          borderColor:"#16a34a",
          borderWidth:2.5,
          borderDash:[5,5],
          pointRadius:3,
          pointHoverRadius:5,
          fill:false,
          tension:0.2
        }
      ]
    },
    options:{
      responsive:true,
      maintainAspectRatio:false,
      interaction:{mode:"index",intersect:false},
      layout:{padding:{top:2,right:8,left:4,bottom:0}},
      scales:{
        x:{
          grid:{
            color:"rgba(148,163,184,0.22)",
            lineWidth:1
          },
          ticks:{
            autoSkip:false,
            maxRotation:0,
            minRotation:0,
            padding:6
          }
        },
        y:{
          beginAtZero:true,
          title:{display:true,text:"金額 (TWD)"},
          grid:{
            color:"rgba(148,163,184,0.22)",
            lineWidth:1
          },
          ticks:{
            padding:6,
            callback:v=>"$"+Number(v).toLocaleString("zh-TW")
          }
        }
      },
      plugins:{
        legend:{
          display:true,
          position:"top",
          align:"center",
          labels:{
            boxWidth:40,
            boxHeight:12,
            padding:18
          }
        },
        tooltip:{
          enabled:true,
          callbacks:{
            title:items=>items.length?labels[items[0].dataIndex]:"",
            label:ctx=>ctx.dataset.label+": $"+Math.round(ctx.parsed.y).toLocaleString("zh-TW")
          }
        }
      }
    }
  });
}document.querySelector("#add").onclick=()=>add();document.querySelector("#run").onclick=simulate;document.querySelector("#export").onclick=()=>{let b=new Blob([JSON.stringify(read(),null,2)],{type:"application/json"}),u=URL.createObjectURL(b),a=document.createElement("a");a.href=u;a.download="mutual_aid_groups.json";a.click();URL.revokeObjectURL(u)};document.querySelector("#import").onchange=e=>{let f=e.target.files[0];if(!f)return;let r=new FileReader;r.onload=()=>{try{document.querySelector("#groups").innerHTML="";JSON.parse(r.result).forEach(add);simulate()}catch{alert("JSON 格式錯誤")}};r.readAsText(f)};try{JSON.parse(localStorage.getItem(KEY)||"[]").forEach(add)}catch{}simulate();