# -*- coding: utf-8 -*-
"""生成单文件热榜趋势看板 src/index.html。

每天由 render-daily.yml 在北京时间 00:30 触发，分析「昨天」一整天的各渠道 CSV：

1. 按渠道 / 排行榜类型还原时间片，输出每个渠道「当天随时间推进」的榜单变化
   （排名轨迹折线图 + 时间滑块快照列表，标题可点击跳转原地址）；
2. 跨渠道汇总所有热榜标题，用 jieba 做「粗粒度、贴主题」的中文关键词云，
   点击单条命中直接跳转，多条命中弹出选择列表再跳转。

数据内联进 HTML，零外部依赖（图表用 ECharts CDN，加载失败有降级）。
历史归档数据不会被修改，本脚本只新增 src/index.html。
"""

import io
import json
import os
import re
import sys
import time

# 让本脚本在任意 cwd 下都能找到 src/utils 下的工具模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "utils"))

from utils import archive_path, logger, read_csv, write_enabled, yesterday_date
from aggregate import _to_number, _safe_rank, _fmt_hot

# 所有渠道。weibo / zhihu 定时停用、github 解析失败，无 csv 时自动跳过。
CHANNELS = ["bilibili", "douyin", "github", "weibo", "zhihu"]

CHANNEL_LABELS = {
    "bilibili": "哔哩哔哩",
    "douyin": "抖音",
    "github": "GitHub",
    "weibo": "微博",
    "zhihu": "知乎",
}

#: 快照列表每帧保留条数上限
TOP_N = 15
#: 排名轨迹图每条类型展示的条目（折线）上限
TRAJ_TOP = 8
#: 关键词云保留关键词上限
KEYWORD_TOP = 60

# 中文停用词（粗粒度分词用，过滤无意义虚词与单字）
STOP = set(
    "的 了 是 在 和 与 及 或 也 都 就 而 你 我 他 她 它 这 那 有 不 没 吗 呢 啊 吧 把 被 让 给 "
    "对 为 以 到 从 向 个 们 中 上 下 后 前 内 外 里 之 其 此 该 各 等 使 将 已 又 很 更 最 太 还 "
    "再 却 但 因 因为 所以 如果 虽然 但是 一个 我们 你们 他们 她们 它们 这个 那个 这些 那些 什么 "
    "怎么 怎样 如何 哪些 自己 大家 别人 没有 不是 就是 还是 这样 那样 一些 一直 已经 可以 应该 "
    "需要 知道 觉得 认为 表示 进行 通过 成为 包括 以及 对于 关于 由于 根据 目前 今天 昨天 明天 "
    "现在 时候 一下 一种 一样 之后 之前 之中 之间 正式 开启 官宣 官宣 网友 表示 回应 曝光 突发 "
    "现场 视频 曝光 热议 冲上 热搜 第一 第二 第三 起来 出来 过来 过去 进去 出去 "
    "一下 已经 开始 朋友 衣服 我们 你们 他们 她们 它们 一直 现在 时候 这种 那种 "
    "一个 一种 一样 这个 那个 这些 那些 这么 那么 怎样 如何 什么 怎么 哪些".split()
)


def _ts_of(row, fallback):
    """挑选代表「抓取批次」的时间戳：优先 datetime（批次），其次 now_time（当天）。

    注意：抖音的 push_time 是每条视频各自的发布时间，不是批次时间，故不采用，
    否则会被切成每片 1 条的碎片。缺失时退化为当天（单快照）。
    """
    dt = row.get("datetime")
    if dt and str(dt).strip():
        return str(dt).strip()
    nt = row.get("now_time")
    if nt and str(nt).strip():
        return str(nt).strip()
    return fallback


def _load_slices(platform, date):
    """读某天 csv，返回 {type: [{"time":..., "items":[row,...]}, ...]}（时间升序）。"""
    csv_path = archive_path(platform, "csv", date)
    rows = read_csv(csv_path)
    if not rows:
        return None
    cells = {}
    for r in rows:
        t = r.get("type") or "unknown"
        ts = _ts_of(r, date)
        cells.setdefault((t, ts), []).append(r)
    result = {}
    for (t, _dt), item_rows in cells.items():
        result.setdefault(t, []).append((_dt, item_rows))
    for t in result:
        result[t].sort(key=lambda x: x[0])
        result[t] = [{"time": dt, "items": item_rows} for dt, item_rows in result[t]]
    return result


def build_channel(platform, date):
    """构建单渠道的展示数据；返回 None 表示无数据。"""
    slices = _load_slices(platform, date)
    if not slices:
        return None

    types_out = {}
    all_ch_items = []
    total_slices = 0

    for type_name, sls in slices.items():
        total_slices += len(sls)
        times = [s["time"] for s in sls]

        snapshots = []
        slice_index = []
        tracks_map = {}

        for s in sls:
            items_sorted = sorted(
                s["items"],
                key=lambda r: (_safe_rank(r.get("index")) or 999, -_to_number(r.get("hot"))),
            )
            m = {}
            for r in items_sorted:
                title = r.get("title")
                if not title:
                    continue
                rank = _safe_rank(r.get("index"))
                hot = _to_number(r.get("hot"))
                url = r.get("url") or ""
                m[title] = (rank, hot)
                tr = tracks_map.setdefault(title, {"title": title, "url": url, "times": []})
                tr["times"].append(s["time"])
                if url:
                    tr["url"] = url
            slice_index.append(m)
            top = items_sorted[:TOP_N]
            snapshots.append(
                {
                    "time": s["time"],
                    "items": [
                        {
                            "rank": _safe_rank(r.get("index")),
                            "title": r.get("title"),
                            "hot": _to_number(r.get("hot")),
                            "url": r.get("url") or "",
                        }
                        for r in top
                    ],
                }
            )

        tracks = []
        max_rank = TOP_N
        for title, tr in tracks_map.items():
            series = []
            for i, tm in enumerate(times):
                if title in slice_index[i]:
                    rk, ht = slice_index[i][title]
                    series.append({"t": tm, "rank": rk or None, "hot": ht, "url": tr["url"]})
                    if rk and rk > max_rank:
                        max_rank = rk
                else:
                    series.append({"t": tm, "rank": None, "hot": None, "url": tr["url"]})
            valid = [x["rank"] for x in series if x["rank"]]
            last = valid[-1] if valid else 999
            first = valid[0] if valid else 999
            tracks.append(
                {
                    "title": title,
                    "url": tr["url"],
                    "series": series,
                    "appear": len(tr["times"]),
                    "last": last,
                    "first": first,
                }
            )

        tracks.sort(key=lambda x: (-x["appear"], x["last"] if x["last"] else 999))
        tracks = tracks[:TRAJ_TOP]

        types_out[type_name] = {
            "times": times,
            "snapshots": snapshots,
            "tracks": tracks,
            "max_rank": max_rank + 1,
            "slice_count": len(sls),
        }

        for s in sls:
            for r in s["items"]:
                t = r.get("title")
                if t:
                    all_ch_items.append(
                        {
                            "channel": platform,
                            "channel_label": CHANNEL_LABELS.get(platform, platform),
                            "type": type_name,
                            "title": t,
                            "url": r.get("url") or "",
                        }
                    )

    return {
        "label": CHANNEL_LABELS.get(platform, platform),
        "types": types_out,
        "types_count": len(types_out),
        "slices_total": total_slices,
        "_items": all_ch_items,
    }


def build_keywords(all_items):
    """跨渠道做粗粒度中文关键词云：extract_tags 取主题词 + 相邻 bigram 取短语，
    每个关键词映射到命中的热榜条目（点击单条直跳、多条弹列表）。
    """
    import jieba
    import jieba.analyse

    corpus = "\n".join(it["title"] for it in all_items if it["title"])

    tags = {}
    try:
        for w, weight in jieba.analyse.extract_tags(
            corpus, topK=120, withWeight=True,
            allowPOS=("ns", "n", "vn", "v", "nz", "nr", "nt", "l", "i", "j"),
        ):
            if len(w) >= 2 and w not in STOP and not w.isdigit():
                tags[w] = tags.get(w, 0.0) + float(weight)
    except Exception as e:  # noqa: BLE001
        logger.warning("extract_tags 失败：%s", e)

    bigrams = {}
    for it in all_items:
        toks = [
            w for w in jieba.lcut(it["title"] or "")
            if len(w) >= 2 and w not in STOP and not w.isdigit() and re.search(r"[\u4e00-\u9fff]", w)
        ]
        for i in range(len(toks) - 1):
            bg = toks[i] + toks[i + 1]
            if len(bg) >= 3 and bg not in STOP:
                bigrams[bg] = bigrams.get(bg, 0) + 1

    candidates = {}
    for w in list(tags.keys()) + list(bigrams.keys()):
        candidates.setdefault(w, 0.0)
        if w in bigrams:
            candidates[w] += float(bigrams[w])
        if w in tags:
            candidates[w] += tags[w]

    out = []
    for w, score in candidates.items():
        if score <= 0:
            continue
        hits = []
        for it in all_items:
            ti = it["title"] or ""
            if w in ti and it["url"]:
                hits.append(
                    {
                        "channel": it["channel"],
                        "channel_label": it["channel_label"],
                        "type": it["type"],
                        "title": ti,
                        "url": it["url"],
                    }
                )
                if len(hits) >= 50:
                    break
        if not hits:
            continue
        out.append({"word": w, "weight": len(hits), "score": round(score, 3), "hits": hits})

    out.sort(key=lambda x: (-x["weight"], -x["score"]))
    return out[:KEYWORD_TOP]


def render_html(payload):
    """把 payload 注入单文件 HTML 模板。"""
    data_json = json.dumps(payload, ensure_ascii=False)
    data_json = data_json.replace("</", "<\\/")

    gen = payload["meta"]["generated_at"]
    date = payload["meta"]["date"]
    nch = len(payload["meta"]["channels"])
    nkw = payload["meta"]["keyword_count"]
    nit = payload["meta"]["item_count"]
    topn = payload["meta"]["top_n"]

    return TEMPLATE.replace("__DATA__", data_json).replace("__GEN__", gen).replace(
        "__DATE__", date
    ).replace("__NCH__", str(nch)).replace("__NKW__", str(nkw)).replace(
        "__NIT__", str(nit)
    ).replace("__TOPN__", str(topn))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>热榜趋势看板 __DATE__</title>
<style>
  :root{
    --bg:#0e0f13; --panel:#15171f; --panel2:#1b1e29; --line:#262a36;
    --txt:#e8eaef; --sub:#9aa0ad; --dim:#6b7180;
    --hot:#ff8a3d; --hot2:#ff5d5d; --cool:#5ec8ff; --ok:#4fd1a0;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--txt);
    font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Segoe UI",Roboto,sans-serif;
    line-height:1.55;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1120px;margin:0 auto;padding:28px 20px 80px}
  header h1{margin:0 0 6px;font-size:26px;letter-spacing:.5px;
    background:linear-gradient(90deg,var(--hot),var(--hot2));-webkit-background-clip:text;background-clip:text;color:transparent}
  .meta{color:var(--sub);font-size:13px;display:flex;gap:14px;flex-wrap:wrap;margin-bottom:6px}
  .meta b{color:var(--txt);font-weight:600}
  .hint{color:var(--dim);font-size:12.5px;margin:2px 0 18px}
  .nav{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 22px}
  .nav a{font-size:13px;color:var(--sub);text-decoration:none;padding:5px 12px;border:1px solid var(--line);border-radius:999px;transition:.15s}
  .nav a:hover{color:var(--txt);border-color:var(--hot);background:var(--panel)}
  section.channel{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px 18px 8px;margin-bottom:26px}
  .ch-head{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:12px}
  .ch-head h2{margin:0;font-size:19px}
  .ch-sub{color:var(--dim);font-size:12.5px}
  .tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
  .tab{background:var(--panel2);color:var(--sub);border:1px solid var(--line);border-radius:9px;
    padding:6px 13px;font-size:13px;cursor:pointer;transition:.15s}
  .tab:hover{color:var(--txt)}
  .tab.active{color:#1a1205;background:linear-gradient(90deg,var(--hot),#ffb070);border-color:transparent;font-weight:600}
  .pane{display:none}
  .pane.active{display:block}
  .chart{width:100%;height:360px;margin-bottom:8px}
  .snap-wrap{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
  .snap-bar{display:flex;align-items:center;gap:12px;margin-bottom:8px}
  .snap-time{font-variant-numeric:tabular-nums;color:var(--hot);font-size:13px;min-width:96px;font-weight:600}
  .snap-count{color:var(--dim);font-size:12px;white-space:nowrap}
  .slider{flex:1;accent-color:var(--hot);cursor:pointer}
  ol.snap-list{list-style:none;margin:6px 0 4px;padding:0;max-height:340px;overflow:auto}
  ol.snap-list li{display:flex;align-items:center;gap:10px;padding:6px 4px;border-bottom:1px dashed var(--line)}
  ol.snap-list li:last-child{border-bottom:none}
  .rank{flex:none;width:26px;height:26px;border-radius:7px;display:grid;place-items:center;font-size:12.5px;font-weight:700;background:var(--panel);color:var(--sub)}
  .rank.r1{background:linear-gradient(135deg,#ff5d5d,#ff8a3d);color:#fff}
  .rank.r2{background:linear-gradient(135deg,#ff9a3d,#ffc46b);color:#3a2400}
  .rank.r3{background:linear-gradient(135deg,#ffd166,#ffe6a3);color:#3a2e00}
  .title{flex:1;color:var(--txt);text-decoration:none;font-size:14px;line-height:1.4}
  .title:hover{color:var(--hot);text-decoration:underline}
  .hot{flex:none;color:var(--ok);font-size:12.5px;font-variant-numeric:tabular-nums;min-width:54px;text-align:right}
  #wordcloud{width:100%;height:440px;background:var(--panel2);border:1px solid var(--line);border-radius:12px}
  .wc-fallback{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;padding:20px;justify-content:center}
  .wc-fallback span{cursor:pointer;line-height:1.2;transition:.12s}
  .wc-fallback span:hover{color:var(--hot)!important;text-decoration:underline}
  .nostate{color:var(--dim);font-size:13px;padding:30px;text-align:center}
  .kwhint{color:var(--dim);font-size:12.5px;margin:6px 0 14px}
  .overlay{position:fixed;inset:0;background:rgba(6,7,10,.72);display:none;align-items:center;justify-content:center;z-index:50;padding:20px}
  .overlay.show{display:flex}
  .modal{background:var(--panel);border:1px solid var(--line);border-radius:14px;max-width:560px;width:100%;max-height:78vh;overflow:auto;padding:18px 20px}
  .modal h3{margin:0 0 4px;font-size:17px}
  .modal .sub{color:var(--dim);font-size:12.5px;margin-bottom:12px}
  .modal a.hit{display:block;padding:9px 10px;border:1px solid var(--line);border-radius:9px;margin-bottom:8px;text-decoration:none;color:var(--txt);transition:.12s}
  .modal a.hit:hover{border-color:var(--hot);background:var(--panel2)}
  .modal .tag{display:inline-block;font-size:11px;color:var(--cool);border:1px solid #244; border-radius:6px;padding:1px 7px;margin-right:8px}
  .modal .close{float:right;cursor:pointer;color:var(--sub);font-size:20px;line-height:1}
  footer{color:var(--dim);font-size:12px;text-align:center;margin-top:30px}
  a{color:var(--cool)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>热榜趋势看板 · <span>__DATE__</span></h1>
    <div class="meta">
      <span>生成时间 <b>__GEN__</b></span>
      <span>渠道 <b>__NCH__</b> 个</span>
      <span>关键词 <b>__NKW__</b> 个</span>
      <span>热榜条目 <b>__NIT__</b> 条</span>
    </div>
    <div class="hint">每个渠道单独展示当天随时间推进的榜单变化：折线图看排名轨迹，拖动滑块看各时刻快照，标题均可点击跳转原地址。下方为跨渠道关键词云。</div>
  </header>

  <nav class="nav" id="nav"></nav>

  <section class="channel">
    <div class="ch-head"><h2>🔥 全局关键词云</h2><span class="ch-sub">点击词跳转；多条命中弹列表选择</span></div>
    <div class="kwhint">关键词经 jieba 粗粒度分词（去虚词、取名词/动词与相邻短语），按命中热榜条数决定字号。单条命中直接跳转，多条命中弹出列表选择后再跳转。</div>
    <div id="wordcloud"></div>
  </section>

  <div id="channels"></div>

  <footer>由 awesome-hot-list 自动生成 · 数据来源各平台公开热榜</footer>
</div>

<div class="overlay" id="overlay">
  <div class="modal">
    <span class="close" id="modalClose">×</span>
    <h3 id="modalTitle"></h3>
    <div class="sub" id="modalSub"></div>
    <div id="modalList"></div>
  </div>
</div>

<script>
const DATA = __DATA__;
const LABELS = DATA.meta.channel_labels;
const TOPN = DATA.meta.top_n;
let charts = {};

function fmtHot(v){ if(v==null) return ''; v=+v; if(v>=1e8) return (v/1e8).toFixed(1)+'亿'; if(v>=1e4) return (v/1e4).toFixed(1)+'万'; return String(Math.round(v)); }
function shortTime(t){ if(!t) return ''; const p=t.split(' '); const time=p[1]?p[1].slice(0,5):''; const date=p[0]?p[0].slice(5):''; return date? (date+' '+time): time; }
function esc(s){ return String(s==null?'':s).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

function buildNav(){
  const nav=document.getElementById('nav');
  DATA.meta.channels.forEach(ch=>{
    const a=document.createElement('a'); a.href='#sec-'+ch; a.textContent=LABELS[ch]||ch; nav.appendChild(a);
  });
  const b=document.createElement('a'); b.href='#wordcloud'; b.textContent='关键词云'; nav.appendChild(b);
}

function chartOption(ch,tn){
  const t=DATA.channels[ch].types[tn];
  const times=t.times.map(shortTime);
  const series=t.tracks.map(tr=>({
    name:tr.title, type:'line', connectNulls:false, showSymbol:true, symbolSize:6,
    emphasis:{focus:'series'},
    data:tr.series.map(p=>({value:p.rank, url:p.url, time:shortTime(p.t)}))
  }));
  return {
    backgroundColor:'transparent',
    textStyle:{color:'#c8ccd6'},
    grid:{left:46,right:20,top:34,bottom:times.length>8?64:48},
    tooltip:{trigger:'item', formatter:p=>{ const d=p.data||{}; return (d.time||'')+'<br/>'+(p.seriesName||'')+'<br/>排名 #'+(d.value==null?'—':d.value)+(d.url?'<br/><span style="color:#ff8a3d">点击跳转 ↗</span>':''); }},
    legend:{type:'scroll', top:0, textStyle:{color:'#9aa0ad', fontSize:11}, pageTextStyle:{color:'#9aa0ad'}, pageIconColor:'#ff8a3d', pageIconInactiveColor:'#444'},
    xAxis:{type:'category', data:times, boundaryGap:false, axisLabel:{color:'#7c828f', fontSize:10, rotate: times.length>8?35:0}, axisLine:{lineStyle:{color:'#2a2e38'}}},
    yAxis:{type:'value', inverse:true, min:1, max:t.max_rank, name:'排名', nameTextStyle:{color:'#7c828f'}, axisLabel:{color:'#7c828f'}, splitLine:{lineStyle:{color:'#1c1f27'}}},
    series:series
  };
}

function initChart(ch,ti,tn){
  const dom=document.getElementById('chart-'+ch+'-'+ti);
  if(!window.echarts){ dom.innerHTML='<div class="nostate">图表库加载失败，下方为可点击快照列表</div>'; return; }
  const chart=echarts.init(dom,null,{renderer:'canvas'});
  chart.setOption(chartOption(ch,tn));
  chart.on('click', p=>{ if(p.data&&p.data.url) window.open(p.data.url,'_blank'); });
  charts[ch+'||'+tn]=chart;
  const slider=document.getElementById('slider-'+ch+'-'+ti);
  slider.addEventListener('input', ()=>renderSnapshot(ch,tn,parseInt(slider.value,10)));
  renderSnapshot(ch,tn,0);
}

function renderSnapshot(ch,tn,idx){
  const t=DATA.channels[ch].types[tn];
  const snap=t.snapshots[idx]||t.snapshots[0];
  document.getElementById('time-'+ch+'-'+tn.replace(/[^\w]/g,'_')).textContent=shortTime(snap.time);
  const list=document.getElementById('list-'+ch+'-'+tn.replace(/[^\w]/g,'_'));
  list.innerHTML=snap.items.map(it=>{
    const r=it.rank||0; const rc=r===1?'r1':r===2?'r2':r===3?'r3':'';
    return '<li><span class="rank '+rc+'">'+(r||'-')+'</span>'+
      '<a class="title" href="'+(it.url||'#')+'" target="_blank" rel="noopener">'+esc(it.title)+'</a>'+
      '<span class="hot">'+(it.hot?fmtHot(it.hot):'')+'</span></li>';
  }).join('');
  const key=ch+'||'+tn;
  if(charts[key]){
    charts[key].setOption({series:[{markLine:{silent:true, symbol:'none', lineStyle:{color:'#ff8a3d',type:'dashed',width:1.5}, label:{show:false}, data:[{xAxis:idx}]}}]});
  }
}

function activateTab(ch,tn,ti){
  const sec=document.getElementById('sec-'+ch);
  sec.querySelectorAll('.tab').forEach((b,i)=>b.classList.toggle('active', i===ti));
  sec.querySelectorAll('.pane').forEach((p,i)=>p.classList.toggle('active', i===ti));
  const pn='pane-'+ch+'-'+ti;
  const pane=document.getElementById(pn);
  if(pane && !pane.dataset.inited){ pane.dataset.inited='1'; initChart(ch,ti,tn); }
}

function buildChannels(){
  const c=document.getElementById('channels');
  DATA.meta.channels.forEach(ch=>{
    const obj=DATA.channels[ch];
    const sec=document.createElement('section'); sec.className='channel'; sec.id='sec-'+ch;
    const head=document.createElement('div'); head.className='ch-head';
    head.innerHTML='<h2>'+(LABELS[ch]||ch)+'</h2><span class="ch-sub">'+obj.types_count+' 类榜单 · '+obj.slices_total+' 次抓取</span>';
    sec.appendChild(head);
    const tabs=document.createElement('div'); tabs.className='tabs';
    const body=document.createElement('div'); body.className='type-body';
    const tns=Object.keys(obj.types);
    tns.forEach((tn,ti)=>{
      const btn=document.createElement('button'); btn.className='tab'+(ti===0?' active':''); btn.textContent=tn;
      btn.onclick=()=>activateTab(ch,tn,ti); tabs.appendChild(btn);
      const pane=document.createElement('div'); pane.className='pane'+(ti===0?' active':''); pane.id='pane-'+ch+'-'+ti;
      const safe=tn.replace(/[^\w]/g,'_');
      pane.innerHTML='<div class="chart" id="chart-'+ch+'-'+ti+'"></div>'+
        '<div class="snap-wrap"><div class="snap-bar"><span class="snap-time" id="time-'+ch+'-'+safe+'"></span>'+
        '<input type="range" class="slider" id="slider-'+ch+'-'+ti+'" min="0" max="'+(obj.types[tn].snapshots.length-1)+'" value="0">'+
        '<span class="snap-count">'+obj.types[tn].snapshots.length+' 帧</span></div>'+
        '<ol class="snap-list" id="list-'+ch+'-'+safe+'"></ol></div>';
      body.appendChild(pane);
    });
    sec.appendChild(tabs); sec.appendChild(body); c.appendChild(sec);
  });
  // 初始化首个渠道首个 pane
  if(DATA.meta.channels.length){
    const ch=DATA.meta.channels[0]; const tn=Object.keys(DATA.channels[ch].types)[0];
    const pane=document.getElementById('pane-'+ch+'-0');
    if(pane){ pane.dataset.inited='1'; initChart(ch,0,tn); }
  }
}

function pick(){ const c=['#ff8a3d','#ff5d5d','#ffd166','#5ec8ff','#9b8cff','#4fd1a0','#ff9ecf','#7ee0ff']; return c[Math.floor(Math.random()*c.length)]; }

function handleHits(hits){
  if(!hits||!hits.length) return;
  if(hits.length===1){ window.open(hits[0].url,'_blank'); return; }
  document.getElementById('modalTitle').textContent='多条命中，选择跳转';
  document.getElementById('modalSub').textContent='共 '+hits.length+' 条相关热榜';
  const list=document.getElementById('modalList');
  list.innerHTML=hits.map(h=>'<a class="hit" href="'+(h.url||'#')+'" target="_blank" rel="noopener"><span class="tag">'+(LABELS[h.channel]||h.channel)+' · '+esc(h.type)+'</span>'+esc(h.title)+'</a>').join('');
  document.getElementById('overlay').classList.add('show');
}

function initWordCloud(){
  const dom=document.getElementById('wordcloud');
  const data=DATA.keywords.map(k=>({name:k.word, value:k.weight, hits:k.hits}));
  if(window.echarts && window.__wc){
    const chart=echarts.init(dom,null,{renderer:'canvas'});
    chart.setOption({
      backgroundColor:'transparent', tooltip:{show:false},
      series:[{type:'wordCloud', shape:'circle', left:0,right:0,top:0,bottom:0,
        sizeRange:[14,68], rotationRange:[-32,32], gridSize:8, drawOutOfBound:false,
        textStyle:{color:()=>pick(), fontFamily:'"PingFang SC","Microsoft YaHei",sans-serif'},
        emphasis:{textStyle:{color:'#ff8a3d'}},
        data:data}]
    });
    chart.on('click', p=>handleHits(p.data.hits));
  } else {
    dom.className='wc-fallback';
    dom.innerHTML=data.map(k=>'<span style="font-size:'+(12+k.weight*1.6)+'px;color:'+pick()+'" data-w="'+esc(k.word)+'">'+esc(k.word)+'</span>').join('');
    dom.querySelectorAll('span').forEach(sp=>{
      sp.onclick=()=>{ const w=sp.getAttribute('data-w'); const kw=DATA.keywords.find(x=>x.word===w); if(kw) handleHits(kw.hits); };
    });
  }
}

document.getElementById('modalClose').onclick=()=>document.getElementById('overlay').classList.remove('show');
document.getElementById('overlay').onclick=e=>{ if(e.target.id==='overlay') e.target.classList.remove('show'); };

function boot(){
  buildNav(); buildChannels();
  if(window.echarts) initWordCloud();
  else document.getElementById('wordcloud').innerHTML='<div class="nostate">图表库加载失败，关键词云以标签云降级展示</div>';
}

const ECHARTS=['https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js','https://unpkg.com/echarts@5.4.3/dist/echarts.min.js','https://cdnjs.cloudflare.com/ajax/libs/echarts/5.4.3/echarts.min.js'];
const WC=['https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js','https://unpkg.com/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js','https://cdnjs.cloudflare.com/ajax/libs/echarts-wordcloud/2.1.0/echarts-wordcloud.min.js'];
function loadOne(urls, ok, fail){
  let i=0; (function next(){ if(i>=urls.length){ fail(); return; }
    const s=document.createElement('script'); s.src=urls[i++];
    s.onload=ok; s.onerror=()=>{ s.remove(); next(); }; document.head.appendChild(s);
  })();
}
loadOne(ECHARTS, function(){
  if(window.echarts){ window.__echartsOk=true;
    loadOne(WC, ()=>{ window.__wc=true; boot(); }, ()=>{ window.__wc=false; boot(); });
  } else { window.__echartsOk=false; boot(); }
}, function(){ window.__echartsOk=false; boot(); });
</script>
</body>
</html>
"""


def main():
    if not write_enabled():
        logger.info("当前为调试模式（HOTLIST_WRITE=0），只分析不落盘")
    date = yesterday_date()
    logger.info("开始渲染 %s 的各渠道数据", date)

    channels_data = {}
    all_items = []
    target_channels = []
    for platform in CHANNELS:
        try:
            ch = build_channel(platform, date)
        except Exception as e:  # noqa: BLE001
            logger.error("[%s] 数据构建失败：%s", platform, e)
            ch = None
        if not ch:
            logger.warning("[%s] %s 无 CSV 数据，跳过", platform, date)
            continue
        target_channels.append(platform)
        channels_data[platform] = {k: v for k, v in ch.items() if k != "_items"}
        all_items.extend(ch["_items"])

    if not target_channels:
        logger.warning("没有任何渠道数据，未生成 index.html")
        return

    keywords = build_keywords(all_items)
    logger.info("关键词云：%d 个", len(keywords))

    payload = {
        "meta": {
            "date": date,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "channels": target_channels,
            "channel_labels": {p: CHANNEL_LABELS.get(p, p) for p in target_channels},
            "top_n": TOP_N,
            "traj_top": TRAJ_TOP,
            "keyword_count": len(keywords),
            "item_count": len(all_items),
        },
        "channels": channels_data,
        "keywords": keywords,
    }

    src_root = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
    out_path = os.path.join(src_root, "index.html")

    if not write_enabled():
        logger.info("[dry-run] 跳过 index.html 落盘: %s", out_path)
        return

    html = render_html(payload)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("已生成 %s（%d 渠道 / %d 关键词）", out_path, len(target_channels), len(keywords))


if __name__ == "__main__":
    main()
