let allEvents = [];
let forceShowWarning = false;

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    loadEvents();
    
    document.getElementById("refresh-btn").addEventListener("click", triggerCrawl);
    document.getElementById("close-modal-btn").addEventListener("click", closeModal);
    document.getElementById("show-low-value-toggle").addEventListener("change", renderGrid);
    
    // Close modal when clicking outside the modal content
    const modalOverlay = document.getElementById("detail-modal");
    modalOverlay.addEventListener("click", (e) => {
        if (e.target === modalOverlay) {
            closeModal();
        }
    });

    // Close modal with Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal();
        }
    });
    
    // Platform filters binding
    document.querySelectorAll("#platform-filters .filter-label").forEach(el => {
        el.addEventListener("click", (e) => {
            document.querySelectorAll("#platform-filters .filter-label").forEach(lbl => lbl.classList.remove("active"));
            e.target.classList.add("active");
            renderGrid();
        });
    });
    
    // Difficulty filters binding
    document.querySelectorAll("#difficulty-filters .filter-label").forEach(el => {
        el.addEventListener("click", (e) => {
            document.querySelectorAll("#difficulty-filters .filter-label").forEach(lbl => lbl.classList.remove("active"));
            e.target.classList.add("active");
            renderGrid();
        });
    });
});

async function loadEvents() {
    const grid = document.getElementById("cards-grid");
    grid.innerHTML = '<div class="grid-loading" style="color: var(--text-sub); grid-column: 1/-1; text-align: center; padding: 5rem 1rem; font-size: 1.1rem; letter-spacing: 0.05em;">正在获取热点数据，请稍候...</div>';
    
    try {
        const res = await fetch("/api/events");
        allEvents = await res.json();
        
        // Detect if fallback mirror was used based on Weibo fallback popularity range
        const hasWeiboFallback = allEvents.some(e => e.platform === "weibo" && e.popularity <= 100000 && e.popularity > 50000);
        const warningBadge = document.getElementById("warning-badge");
        
        if (hasWeiboFallback || forceShowWarning) {
            warningBadge.classList.remove("hide");
        } else {
            warningBadge.classList.add("hide");
        }
        
        renderGrid();
    } catch (e) {
        grid.innerHTML = '<div class="grid-error" style="color: var(--accent-red); grid-column: 1/-1; text-align: center; padding: 5rem 1rem; font-size: 1.1rem;">拉取数据失败，请检查后端运行状态。</div>';
    }
}

async function triggerCrawl() {
    const btn = document.getElementById("refresh-btn");
    btn.disabled = true;
    btn.textContent = "🔄 爬取并清理中...";
    
    try {
        const res = await fetch("/api/trigger-crawl", { method: "POST" });
        const data = await res.json();
        
        if (data.status === "success" && data.summary) {
            const sum = data.summary;
            if (sum.weibo_fallback || sum.zhihu_fallback || sum.zhihu_pin_fallback) {
                forceShowWarning = true;
            } else {
                forceShowWarning = false;
            }
        }
        
        await loadEvents();
    } catch (e) {
        alert("刷新抓取失败，请检查网络或后端服务。");
    } finally {
        btn.disabled = false;
        btn.textContent = "🔄 刷新抓取热点";
    }
}

function renderGrid() {
    const grid = document.getElementById("cards-grid");
    grid.innerHTML = "";
    
    // Read filter configuration
    const selectedPlatform = document.querySelector("#platform-filters .filter-label.active").dataset.platform;
    const selectedDifficulty = document.querySelector("#difficulty-filters .filter-label.active").dataset.difficulty;
    const showLowValue = document.getElementById("show-low-value-toggle").checked;
    
    const filtered = allEvents.filter(e => {
        // 1. Platform Filter
        if (selectedPlatform !== "all" && e.platform !== selectedPlatform) return false;
        
        // 2. Status / Low Value Filter
        if (e.status === "low_value" && !showLowValue) return false;
        
        // 3. Difficulty Filter
        if (selectedDifficulty !== "all" && e.difficulty !== selectedDifficulty) return false;
        
        return true;
    });
    
    if (filtered.length === 0) {
        grid.innerHTML = '<div style="color: var(--text-muted); grid-column: 1/-1; text-align: center; padding: 5rem 1rem; font-size: 1.1rem;">暂无匹配的数据。</div>';
        return;
    }
    
    filtered.forEach(e => {
        const card = document.createElement("div");
        // Add platform-hover class for tailored glow colors
        card.className = `card-item ${e.platform}-hover`;
        
        let statusHtml = "";
        let scoreHtml = "";
        let btnHtml = "";
        let isClickable = false;
        
        // Set up status badge & values
        if (e.status === "analyzed") {
            statusHtml = `<span class="status-badge analyzed">已分析</span>`;
            
            let valClass = "low";
            if (e.value_score >= 8) valClass = "high";
            else if (e.value_score >= 6) valClass = "med";
            
            scoreHtml = `<span class="score-badge ${valClass}">⭐ ${e.value_score} 分</span>`;
            isClickable = true;
        } else if (e.status === "low_value") {
            statusHtml = `<span class="status-badge low_value">低价值</span>`;
            scoreHtml = `<span class="score-badge low">💤 ${e.value_score} 分</span>`;
            isClickable = true;
        } else if (e.status === "failed") {
            statusHtml = `<span class="status-badge failed">分析失败</span>`;
            btnHtml = `<button class="analyze-btn">🔄 重试</button>`;
        } else {
            statusHtml = `<span class="status-badge pending">待分析</span>`;
            btnHtml = `<button class="analyze-btn">🧠 AI 分析</button>`;
        }
        
        // Platform localized text
        let platformName = "微博";
        if (e.platform === "zhihu") platformName = "知乎";
        else if (e.platform === "zhihu_pin") platformName = "想法";
        
        card.innerHTML = `
            <div>
                <div class="card-top">
                    <div class="platform-badges-wrapper">
                        <span class="platform-badge ${e.platform}">${platformName}</span>
                        ${statusHtml}
                    </div>
                    ${scoreHtml}
                </div>
                <div class="card-title" title="${escapeHtml(e.title)}">${escapeHtml(e.title)}</div>
                <div class="card-desc">${escapeHtml(e.analysis_summary || "暂无 AI 分析报告，请点击下方进行深度需求挖掘。")}</div>
            </div>
            <div class="card-meta">
                <span class="popularity-text">🔥 指数: ${e.popularity ? e.popularity.toLocaleString() : '0'}</span>
                ${btnHtml}
            </div>
        `;
        
        const analyzeBtn = card.querySelector(".analyze-btn");
        if (analyzeBtn) {
            analyzeBtn.addEventListener("click", (event) => {
                startAnalysis(event, e.id, e.title, e.platform);
            });
        }
        
        if (isClickable) {
            card.style.cursor = "pointer";
            card.addEventListener("click", () => showDetails(e));
        } else {
            card.style.cursor = "default";
        }
        
        grid.appendChild(card);
    });
}

async function startAnalysis(event, eventId, title, platform) {
    event.stopPropagation(); // Prevent trigger details modal on card click
    
    const btn = event.target;
    btn.disabled = true;
    const originalText = btn.textContent;
    btn.textContent = "⚡ 分析中...";
    btn.classList.add("loading");
    
    try {
        const res = await fetch(`/api/events/${eventId}/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, platform })
        });
        const data = await res.json();
        
        if (data.status === "success") {
            await loadEvents();
        } else {
            alert("AI 分析出错，请确认后重试。");
        }
    } catch (e) {
        alert("请求异常，请检查后端 API 与网络连接。");
    } finally {
        btn.disabled = false;
        btn.textContent = originalText;
        btn.classList.remove("loading");
    }
}

function showDetails(e) {
    document.getElementById("modal-title").textContent = e.title;
    
    let platformName = "微博热搜";
    if (e.platform === "zhihu") platformName = "知乎热榜";
    else if (e.platform === "zhihu_pin") platformName = "知乎想法";
    
    const platformEl = document.getElementById("modal-platform");
    platformEl.textContent = platformName;
    platformEl.className = `modal-platform platform-badge ${e.platform}`;
    
    document.getElementById("modal-url").href = e.url || "#";
    document.getElementById("modal-audience").textContent = e.target_audience || "无";
    document.getElementById("modal-pain").textContent = e.pain_point || "无";
    document.getElementById("modal-concept").textContent = e.product_concept || "无";
    
    const difficultyMap = {
        "easy": "简单 (插件/脚本)",
        "medium": "中等 (小程序/网站)",
        "hard": "困难 (深研/AI/大数据)"
    };
    document.getElementById("modal-difficulty").textContent = difficultyMap[e.difficulty] || e.difficulty || "未知";
    
    const scoreEl = document.getElementById("modal-score");
    scoreEl.textContent = `${e.value_score} 分`;
    
    if (e.value_score >= 8) {
        scoreEl.className = "val score-high";
    } else if (e.value_score >= 6) {
        scoreEl.className = "val score-med";
    } else {
        scoreEl.className = "val score-low";
    }
    
    document.getElementById("detail-modal").classList.remove("hide");
}

function closeModal() {
    document.getElementById("detail-modal").classList.add("hide");
}

// Simple HTML escaping helper to prevent XSS issues
function escapeHtml(str) {
    if (!str) return "";
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
