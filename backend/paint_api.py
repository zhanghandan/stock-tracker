"""
AI绘画 - ModelScope Z-Image-Turbo
"""
import time
import os
import json
import asyncio
import hashlib
import httpx
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Body, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from loguru import logger

paint_router = APIRouter(prefix="/paint", tags=["paint"])

# ── 配置 ──
TOKEN_FILE = "/opt/.modelscope_token"
DATA_DIR = Path("/opt/stock-tracker/data/paint")
DATA_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = DATA_DIR / "images"
IMG_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "history.json"

DOUBAO_API = "https://ark.cn-beijing.volces.com/api/v3/responses"
DOUBAO_MODEL = "doubao-seed-2-0-lite-260428"
MODELSCOPE_API = "https://api-inference.modelscope.cn/v1"

def _load_doubao_key():
    try:
        with open("/opt/.doubao_key") as f:
            return f.read().strip()
    except:
        return os.getenv("DOUBAO_KEY", "")

def _load_token():
    try:
        with open(TOKEN_FILE) as f:
            return f.read().strip()
    except:
        return os.getenv("MODELSCOPE_TOKEN", "")

# ── 风格预设 ──
STYLES = {
    "realistic": {
        "name": "写实摄影",
        "icon": "📷",
        "prefix": "photorealistic, highly detailed, professional photography, 8k, natural lighting",
    },
    "anime": {
        "name": "动漫风格",
        "icon": "🎌",
        "prefix": "anime style, manga art, studio ghibli inspired, vibrant colors",
    },
    "oil": {
        "name": "古典油画",
        "icon": "🖼️",
        "prefix": "oil painting, classical fine art, renaissance style, rich textures",
    },
    "cyberpunk": {
        "name": "赛博朋克",
        "icon": "🌃",
        "prefix": "cyberpunk, neon lights, futuristic city, blade runner aesthetic, rain",
    },
    "watercolor": {
        "name": "水彩插画",
        "icon": "🎨",
        "prefix": "watercolor painting, soft pastel colors, artistic illustration, dreamy",
    },
    "sketch": {
        "name": "素描线稿",
        "icon": "✏️",
        "prefix": "pencil sketch, detailed line art, hand drawn, monochrome, artistic",
    },
}

# ── 历史记录管理 ──
def _load_history():
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return []

def _save_history(history):
    HISTORY_FILE.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")

def _add_history(entry):
    h = _load_history()
    h.insert(0, entry)
    if len(h) > 100:  # 最多保留100条
        # 删除最旧图片
        for old in h[100:]:
            old_path = IMG_DIR / old.get("filename", "")
            if old_path.exists():
                old_path.unlink()
        h = h[:100]
    _save_history(h)

# ── 绘画页面 HTML ──
PAINT_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
<title>AI 绘画</title>
<style>
:root {
  --bg: #0d0d0f;
  --card: #1a1a1f;
  --accent: #7c3aed;
  --accent2: #a78bfa;
  --text: #e4e4e7;
  --text2: #71717a;
  --border: #27272a;
  --radius: 14px;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: var(--bg); color: var(--text);
  font-family: -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  min-height: 100dvh;
  padding-bottom: env(safe-area-inset-bottom, 16px);
}
.container { max-width: 520px; margin: 0 auto; padding: 16px; }

/* Header */
.header {
  text-align: center; padding: 20px 0 8px;
}
.header h1 { font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }
.header h1 span { background: linear-gradient(135deg, #7c3aed, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.header p { font-size: 13px; color: var(--text2); margin-top: 4px; }

/* Input */
.prompt-area {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 12px;
  margin-bottom: 12px;
}
.prompt-area textarea {
  width: 100%; background: transparent; border: none;
  color: var(--text); font-size: 15px; font-family: inherit;
  resize: none; outline: none; min-height: 60px;
}
.prompt-area textarea::placeholder { color: var(--text2); }

/* Styles */
.styles-row {
  display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;
}
.style-btn {
  padding: 8px 14px; border-radius: 20px; border: 1px solid var(--border);
  background: var(--card); color: var(--text2); font-size: 13px;
  cursor: pointer; transition: all 0.15s; white-space: nowrap;
}
.style-btn:active { transform: scale(0.95); }
.style-btn.active {
  border-color: var(--accent); background: #7c3aed1a;
  color: var(--accent2); font-weight: 600;
}

/* Generate button */
.gen-btn {
  width: 100%; padding: 14px; border: none; border-radius: var(--radius);
  background: linear-gradient(135deg, #7c3aed, #6d28d9);
  color: #fff; font-size: 16px; font-weight: 700;
  cursor: pointer; transition: all 0.15s; margin-bottom: 16px;
}
.gen-btn:active { transform: scale(0.97); }
.gen-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.gen-btn .spinner {
  display: none; width: 20px; height: 20px; border: 2px solid #fff3;
  border-top-color: #fff; border-radius: 50%; animation: spin 0.8s linear infinite;
  margin-right: 8px; vertical-align: middle;
}
.gen-btn.loading .spinner { display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Result */
.result-area { margin-bottom: 20px; }
.result-area img {
  width: 100%; border-radius: var(--radius);
  box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  cursor: pointer;
}
.result-info {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 4px; font-size: 12px; color: var(--text2);
}
.result-info .download {
  color: var(--accent2); cursor: pointer; text-decoration: none;
}

/* History */
.history-title {
  font-size: 16px; font-weight: 700; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.history-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
}
.history-item {
  aspect-ratio: 1; border-radius: 10px; overflow: hidden;
  background: var(--card); cursor: pointer; position: relative;
  transition: transform 0.15s;
}
.history-item:active { transform: scale(0.95); }
.history-item img {
  width: 100%; height: 100%; object-fit: cover;
}
.history-item .overlay {
  position: absolute; bottom: 0; left: 0; right: 0;
  padding: 4px 6px; background: linear-gradient(transparent, rgba(0,0,0,0.8));
  font-size: 10px; color: #ccc; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.history-item .delete {
  position: absolute; top: 4px; right: 4px;
  width: 22px; height: 22px; border-radius: 50%;
  background: rgba(0,0,0,0.6); color: #fff;
  border: none; font-size: 14px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.2s;
}
.history-item:hover .delete { opacity: 1; }
@media (hover: none) { .history-item .delete { opacity: 0.7; } }

/* Enhance button */
.enhance-btn {
  padding: 6px 14px; border-radius: 16px;
  border: 1px solid var(--accent); background: transparent;
  color: var(--accent2); font-size: 12px; cursor: pointer;
  transition: all 0.15s;
}
.enhance-btn:active { transform: scale(0.95); }
.enhance-btn:disabled { opacity: 0.5; }
.enhance-btn.working { background: #7c3aed1a; }

/* Review section */
.review-box {
  background: var(--card); border: 1px solid var(--accent); border-radius: var(--radius);
  padding: 12px 14px; margin-bottom: 16px; display: none;
}
.review-box.show { display: block; animation: fadeIn 0.3s; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } }
.review-box .review-title {
  font-size: 13px; font-weight: 700; color: var(--accent2); margin-bottom: 6px;
}
.review-box .review-text { font-size: 13px; color: var(--text); line-height: 1.7; }

/* Modal */
.modal {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.95);
  z-index: 999; flex-direction: column; align-items: center;
  padding: 20px;
}
.modal.show { display: flex; }
.modal img {
  max-width: 100%; max-height: 70vh; border-radius: 12px;
  margin-top: auto;
}
.modal-info {
  color: var(--text2); font-size: 13px; text-align: center;
  padding: 16px; margin-bottom: auto;
}
.modal-close {
  position: absolute; top: 16px; right: 16px;
  width: 36px; height: 36px; border-radius: 50%;
  background: rgba(255,255,255,0.1); border: none;
  color: #fff; font-size: 20px; cursor: pointer;
}

/* Loading overlay */
.loading-overlay {
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7);
  z-index: 998; align-items: center; justify-content: center; flex-direction: column; gap: 16px;
}
.loading-overlay.show { display: flex; }
.loading-spinner {
  width: 48px; height: 48px; border: 3px solid #ffffff22;
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
.loading-text { color: var(--text2); font-size: 14px; }
</style>
</head>
<body>

<div class="container">
  <div class="header">
    <h1><span>AI</span> 绘画</h1>
    <p>描述你想要的画面，AI为你创作</p>
  </div>

  <div class="prompt-area">
    <textarea id="promptInput" placeholder="输入画面描述，如：一只猫在月球上弹钢琴，星空背景..." maxlength="500"></textarea>
    <div style="display:flex;justify-content:flex-end;margin-top:8px">
      <button class="enhance-btn" onclick="enhancePrompt()" id="enhanceBtn">🤖 AI润色</button>
    </div>
  </div>

  <div class="styles-row" id="stylesRow"></div>

  <button class="gen-btn" id="genBtn" onclick="generate()">
    <span class="spinner"></span> <span id="genText">✨ 生成图片</span>
  </button>

  <div class="result-area" id="resultArea" style="display:none">
    <img id="resultImage" src="" onclick="openModal(this.src)" />
    <div class="result-info">
      <span id="resultPrompt"></span>
      <div style="display:flex;gap:12px">
        <a class="download" id="resultDownload" download>💾 保存</a>
        <span style="color:var(--accent2);cursor:pointer;font-size:12px" onclick="reviewImage()" id="reviewBtn">🤖 AI评画</span>
      </div>
    </div>
  </div>

  <div class="review-box" id="reviewBox">
    <div class="review-title">🤖 AI 评画</div>
    <div class="review-text" id="reviewText"></div>
  </div>

  <div class="history-title">📋 历史记录</div>
  <div class="history-grid" id="historyGrid">
    <div style="grid-column:1/-1;text-align:center;color:var(--text2);padding:32px;font-size:14px">还没有作品，快去创作吧 ✨</div>
  </div>
</div>

<div class="loading-overlay" id="loadingOverlay">
  <div class="loading-spinner"></div>
  <div class="loading-text">AI正在绘画中... 约15秒</div>
</div>

<div class="modal" id="imageModal" onclick="this.classList.remove('show')">
  <button class="modal-close" onclick="document.getElementById('imageModal').classList.remove('show')">&times;</button>
  <img id="modalImage" src="" />
  <div class="modal-info" id="modalInfo"></div>
</div>

<script>
var currentStyle = 'realistic';
var generating = false;

// ── 渲染风格按钮 ──
var styles = %STYLES_JSON%;
var stylesHtml = '';
for (var key in styles) {
  var s = styles[key];
  stylesHtml += '<button class="style-btn' + (key === currentStyle ? ' active' : '') +
    '" data-style="' + key + '" onclick="selectStyle(\'' + key + '\')">' + s.icon + ' ' + s.name + '</button>';
}
document.getElementById('stylesRow').innerHTML = stylesHtml;

function selectStyle(key) {
  currentStyle = key;
  document.querySelectorAll('.style-btn').forEach(function(b) {
    b.classList.toggle('active', b.dataset.style === key);
  });
}

// ── 生成 ──
async function generate() {
  var prompt = document.getElementById('promptInput').value.trim();
  if (!prompt || generating) return;
  generating = true;

  var btn = document.getElementById('genBtn');
  btn.classList.add('loading');
  document.getElementById('genText').textContent = '生成中...';

  try {
    var res = await fetch('/paint/gen', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, style: currentStyle })
    });

    if (res.ok) {
      lastImgId = res.headers.get('X-Image-Id') || '';
      document.getElementById('reviewBox').classList.remove('show');
      var blob = await res.blob();
      var url = URL.createObjectURL(blob);
      document.getElementById('resultArea').style.display = 'block';
      document.getElementById('resultImage').src = url;
      document.getElementById('resultPrompt').textContent = prompt.substring(0, 40) + (prompt.length > 40 ? '...' : '');
      var dl = document.getElementById('resultDownload');
      dl.href = url;
      dl.download = 'ai_paint_' + Date.now() + '.png';
      document.getElementById('resultArea').scrollIntoView({ behavior: 'smooth' });
      loadHistory();
    } else {
      var err = await res.json();
      alert('生成失败: ' + (err.detail || '未知错误'));
    }
  } catch (e) {
    alert('网络错误，请重试');
  }

  btn.classList.remove('loading');
  document.getElementById('genText').textContent = '✨ 生成图片';
  generating = false;
}

// ── Enter发送 ──
document.getElementById('promptInput').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    generate();
  }
});

// ── 历史记录 ──
async function loadHistory() {
  try {
    var res = await fetch('/paint/history');
    var data = await res.json();
    var grid = document.getElementById('historyGrid');
    if (!data.length) {
      grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:var(--text2);padding:32px;font-size:14px">还没有作品，快去创作吧 ✨</div>';
      return;
    }
    var html = '';
    data.forEach(function(item) {
      var prompt = (item.prompt || '').substring(0, 30);
      html += '<div class="history-item" onclick="openModal(\'/paint/img/' + item.id + '\', \'' + escapeHtml(item.prompt || '') + '\', \'' + (item.style_name || '') + '\')">' +
        '<img src="/paint/img/' + item.id + '" loading="lazy" />' +
        '<div class="overlay">' + prompt + '</div>' +
        '<button class="delete" onclick="event.stopPropagation();deleteImage(\'' + item.id + '\')">×</button>' +
        '</div>';
    });
    grid.innerHTML = html;
  } catch (e) {}
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function deleteImage(id) {
  if (!confirm('删除这张画？')) return;
  try {
    await fetch('/paint/img/' + id, { method: 'DELETE' });
    loadHistory();
  } catch (e) {}
}

function openModal(src, prompt, style) {
  document.getElementById('modalImage').src = src;
  document.getElementById('modalInfo').textContent = (prompt || '') + (style ? ' · ' + style : '');
  document.getElementById('imageModal').classList.add('show');
}

// ── AI润色 ──
var lastImgId = null;
var reviewing = false;

async function enhancePrompt() {
  var input = document.getElementById('promptInput');
  var prompt = input.value.trim();
  if (!prompt) return;

  var btn = document.getElementById('enhanceBtn');
  btn.textContent = '⏳ 润色中...';
  btn.disabled = true;
  btn.classList.add('working');

  try {
    var res = await fetch('/paint/enhance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt })
    });
    if (res.ok) {
      var data = await res.json();
      input.value = data.enhanced;
    }
  } catch (e) {}

  btn.textContent = '🤖 AI润色';
  btn.disabled = false;
  btn.classList.remove('working');
}

// ── AI评画 ──
async function reviewImage() {
  if (!lastImgId || reviewing) return;
  reviewing = true;
  var box = document.getElementById('reviewBox');
  var text = document.getElementById('reviewText');
  var btn = document.getElementById('reviewBtn');
  box.classList.add('show');
  text.textContent = '正在分析...';
  btn.textContent = '⏳ 分析中...';

  try {
    var res = await fetch('/paint/review/' + lastImgId);
    if (res.ok) {
      var data = await res.json();
      text.textContent = data.review;
    } else {
      text.textContent = '评画失败，请重试';
    }
  } catch (e) {
    text.textContent = '网络错误';
  }

  btn.textContent = '🤖 AI评画';
  reviewing = false;
}

// ── 初始加载 ──
loadHistory();
</script>
</body>
</html>
"""

# ── 渲染HTML（注入styles JSON） ──
def _get_html():
    return PAINT_HTML.replace("%STYLES_JSON%", json.dumps(
        {k: {"name": v["name"], "icon": v["icon"]} for k, v in STYLES.items()},
        ensure_ascii=False
    ))

# ── 页面 ──
@paint_router.get("/", response_class=HTMLResponse)
@paint_router.get("", response_class=HTMLResponse)
async def paint_page():
    return HTMLResponse(_get_html())

# ── 生图 API ──
@paint_router.post("/gen")
async def paint_generate(payload: dict = Body(...)):
    prompt = payload.get("prompt", "").strip()
    style_key = payload.get("style", "realistic")

    if not prompt:
        raise HTTPException(status_code=400, detail="请输入画面描述")
    if len(prompt) > 500:
        raise HTTPException(status_code=400, detail="描述不能超过500字")

    style = STYLES.get(style_key, STYLES["realistic"])
    full_prompt = f"{style['prefix']}, {prompt}"

    token = _load_token()
    if not token:
        raise HTTPException(status_code=503, detail="ModelScope Token未配置")

    async with httpx.AsyncClient(timeout=60) as client:
        # Step 1: 提交
        submit = await client.post(
            f"{MODELSCOPE_API}/images/generations",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-ModelScope-Async-Mode": "true",
            },
            json={"model": "Tongyi-MAI/Z-Image-Turbo", "prompt": full_prompt, "height": 512, "width": 512},
        )
        if submit.status_code != 200:
            raise HTTPException(status_code=502, detail=f"提交失败: {submit.status_code}")

        task_id = submit.json().get("task_id", "")
        logger.info(f"Paint task: {task_id} style={style_key} prompt={prompt[:40]}")

        # Step 2: 轮询
        for _ in range(60):
            await asyncio.sleep(2)
            poll = await client.get(
                f"{MODELSCOPE_API}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {token}", "X-ModelScope-Task-Type": "image_generation"},
            )
            if poll.status_code != 200:
                continue
            data = poll.json()
            status = data.get("task_status", "")

            if status == "SUCCEED":
                images = data.get("output_images", [])
                if images:
                    img_url = images[0] if isinstance(images[0], str) else images[0].get("url", "")
                    if img_url:
                        img_resp = await client.get(img_url)
                        img_data = img_resp.content

                        # 保存到本地
                        img_id = hashlib.md5(f"{task_id}{time.time()}".encode()).hexdigest()[:12]
                        filename = f"{img_id}.png"
                        filepath = IMG_DIR / filename
                        filepath.write_bytes(img_data)

                        # 记录历史
                        _add_history({
                            "id": img_id,
                            "prompt": prompt,
                            "full_prompt": full_prompt,
                            "style": style_key,
                            "style_name": style["name"],
                            "filename": filename,
                            "created_at": datetime.now().isoformat(),
                        })

                        logger.info(f"Paint done: {img_id} ({len(img_data)} bytes)")
                        return StreamingResponse(
                            iter([img_data]),
                            media_type="image/png",
                            headers={"Cache-Control": "no-cache", "X-Image-Id": img_id},
                        )
                raise HTTPException(status_code=502, detail="生图完成但无图片")

            elif status == "FAILED":
                raise HTTPException(status_code=502, detail="生成失败，换个描述试试")

        raise HTTPException(status_code=503, detail="生图超时(120秒)，请重试")

# ── 豆包润色提示词 ──
@paint_router.post("/enhance")
async def paint_enhance(payload: dict = Body(...)):
    prompt = payload.get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="empty")

    doubao_key = _load_doubao_key()
    if not doubao_key:
        raise HTTPException(status_code=503, detail="豆包API未配置")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DOUBAO_API,
            headers={"Authorization": f"Bearer {doubao_key}", "Content-Type": "application/json"},
            json={
                "model": DOUBAO_MODEL,
                "input": [{"role": "user", "content": [
                    {"type": "input_text", "text": f"你是一个AI绘画提示词专家。请把下面这个画面描述扩展成一个更详细、更适合AI绘画的英文提示词。加入光线、构图、风格、细节描述。只返回英文提示词，不要解释。\n\n原始描述：{prompt}"}
                ]}],
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return {"enhanced": c["text"].strip()}
        raise HTTPException(status_code=502, detail="润色失败")

# ── 豆包AI评画 ──
@paint_router.get("/review/{img_id}")
async def paint_review(img_id: str):
    h = _load_history()
    filepath = None
    img_prompt = ""
    for item in h:
        if item["id"] == img_id:
            filepath = IMG_DIR / item["filename"]
            img_prompt = item.get("prompt", "")
            break
    if not filepath or not filepath.exists():
        raise HTTPException(status_code=404, detail="图片不存在")

    doubao_key = _load_doubao_key()
    if not doubao_key:
        raise HTTPException(status_code=503, detail="豆包API未配置")

    import base64
    img_data = base64.b64encode(filepath.read_bytes()).decode()
    img_url = f"data:image/png;base64,{img_data}"

    review_prompt = f"这张AI绘画的原始描述是：「{img_prompt}」。请从构图、色彩、光影、细节还原度、艺术感五个维度简要点评这幅画（80字以内），语气像艺术评论家，用中文。"

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            DOUBAO_API,
            headers={"Authorization": f"Bearer {doubao_key}", "Content-Type": "application/json"},
            json={
                "model": DOUBAO_MODEL,
                "input": [{"role": "user", "content": [
                    {"type": "input_image", "image_url": img_url},
                    {"type": "input_text", "text": review_prompt},
                ]}],
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("output", []):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if c.get("type") == "output_text":
                            return {"review": c["text"].strip(), "img_id": img_id}
        raise HTTPException(status_code=502, detail="评画失败")

# ── 历史 API ──
@paint_router.get("/history")
async def paint_history():
    h = _load_history()
    return [
        {
            "id": item["id"],
            "prompt": item["prompt"],
            "style": item["style"],
            "style_name": item.get("style_name", ""),
            "created_at": item["created_at"],
        }
        for item in h
    ]

# ── 图片文件 ──
@paint_router.get("/img/{img_id}")
async def paint_image(img_id: str):
    h = _load_history()
    for item in h:
        if item["id"] == img_id:
            filepath = IMG_DIR / item["filename"]
            if filepath.exists():
                return FileResponse(filepath, media_type="image/png")
            break
    raise HTTPException(status_code=404, detail="图片不存在")

@paint_router.delete("/img/{img_id}")
async def paint_delete(img_id: str):
    h = _load_history()
    for i, item in enumerate(h):
        if item["id"] == img_id:
            filepath = IMG_DIR / item["filename"]
            if filepath.exists():
                filepath.unlink()
            h.pop(i)
            _save_history(h)
            return {"ok": True}
    raise HTTPException(status_code=404, detail="图片不存在")
