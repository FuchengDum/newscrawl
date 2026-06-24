let allEvents = [];
let forceShowWarning = false;
let selectedDate = null;
let selectedStatus = 'all';
let selectedDifficulty = 'all';
let selectedPlatform = 'all';
let availableDates = [];
let batchPollTimer = null;
let reportMarkdownCache = '';

// Initialization
document.addEventListener("DOMContentLoaded", () => {
    loadDates();
    
    document.getElementById("refresh-btn").addEventListener("click", triggerCrawl);
    document.getElementById("close-modal-btn").addEventListener("click", closeModal);
    document.getElementById("show-low-value-toggle").addEventListener("change", loadEvents);
    document.getElementById("batch-analyze-btn").addEventListener("click", batchAnalyze);
    document.getElementById("generate-report-btn").addEventListener("click", generateReport);
    document.getElementById("close-report-modal-btn").addEventListener("click", closeReportModal);
    document.getElementById("download-report-btn").addEventListener("click", downloadReport);
    
    // Close modal when clicking outside the modal content
    const modalOverlay = document.getElementById("detail-modal");
    modalOverlay.addEventListener("click", (e) => {
        if (e.target === modalOverlay) {
            closeModal();
        }
    });

    const reportOverlay = document.getElementById("report-modal");
    reportOverlay.addEventListener("click", (e) => {
        if (e.target === reportOverlay) {
            closeReportModal();
        }
    });

    // Close modal with Escape key
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModal();
            closeReportModal();
        }
    });
    
    // Platform filters binding
    document.querySelectorAll("#platform-filters .filter-label").forEach(el => {
        el.addEventListener("click", (e) => {
            document.querySelectorAll("#platform-filters .filter-label").forEach(lbl => lbl.classList.remove("active"));
            e.target.classList.add("active");
            selectedPlatform = e.target.dataset.platform;
            loadEvents();
        });
    });
    
    // Status filters binding
    document.querySelectorAll("#status-filters .filter-label").forEach(el => {
        el.addEventListener("click", (e) => {
            document.querySelectorAll("#status-filters .filter-label").forEach(lbl => lbl.classList.remove("active"));
            e.target.classList.add("active");
            selectedStatus = e.target.dataset.status;
            updateToggleState();
            loadEvents();
        });
    });
    
    // Difficulty filters binding
    document.querySelectorAll("#difficulty-filters .filter-label").forEach(el => {
        el.addEventListener("click", (e) => {
            document.querySelectorAll("#difficulty-filters .filter-label").forEach(lbl => lbl.classList.remove("active"));
            e.target.classList.add("active");
            selectedDifficulty = e.target.dataset.difficulty;
            loadEvents();
        });
    });
});

function updateToggleState() {
    const toggle = document.getElementById("show-low-value-toggle");
    const wrapper = document.getElementById("toggle-wrapper");
    if (selectedStatus !== 'all') {
        toggle.disabled = true;
        wrapper.classList.add("toggle-disabled");
    } else {
        toggle.disabled = false;
        wrapper.classList.remove("toggle-disabled");
    }
}

async function loadDates() {
    try {
        const res = await fetch("/api/dates");
        const data = await res.json();
        availableDates = data.dates || [];
        renderDateFilters();
        // After rendering dates, load events
        loadEvents();
    } catch (e) {
        console.error("Failed to load dates:", e);
        loadEvents();
    }
}

function renderDateFilters() {
    const container = document.getElementById("date-filters");
    container.innerHTML = "";

    if (availableDates.length === 0) {
        container.innerHTML = '<span class="no-data-hint">暂无数据</span>';
        return;
    }

    // Determine today's date in UTC+8
    const now = new Date();
    const utc8 = new Date(now.getTime() + 8 * 60 * 60 * 1000);
    const todayStr = utc8.toISOString().slice(0, 10);

    // Default: select today if available, otherwise the most recent date
    if (availableDates.includes(todayStr)) {
        selectedDate = todayStr;
    } else {
        selectedDate = availableDates[0]; // most recent
    }

    availableDates.forEach(d => {
        const label = document.createElement("label");
        label.className = "filter-label" + (d === selectedDate ? " active" : "");
        label.dataset.date = d;
        // Format display: show weekday
        const dateObj = new Date(d + "T00:00:00+08:00");
        const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
        const weekday = weekdays[dateObj.getDay()];
        label.textContent = `${d} (周${weekday})`;
        label.addEventListener("click", () => {
            document.querySelectorAll("#date-filters .filter-label").forEach(lbl => lbl.classList.remove("active"));
            label.classList.add("active");
            selectedDate = d;
            loadEvents();
        });
        container.appendChild(label);
    });
}

async function loadEvents() {
    const grid = document.getElementById("cards-grid");
    grid.innerHTML = '<div class="grid-loading" style="color: var(--text-sub); grid-column: 1/-1; text-align: center; padding: 5rem 1rem; font-size: 1.1rem; letter-spacing: 0.05em;">正在获取热点数据，请稍候...</div>';
    
    try {
        const showLowValue = document.getElementById("show-low-value-toggle").checked;
        const params = new URLSearchParams();
        if (selectedDate) params.set("date", selectedDate);
        if (selectedPlatform !== "all") params.set("platform", selectedPlatform);
        if (selectedStatus !== "all") params.set("status", selectedStatus);
        if (selectedDifficulty !== "all") params.set("difficulty", selectedDifficulty);
        params.set("show_low_value", showLowValue);

        const res = await fetch(`/api/events?${params.toString()}`);
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
        
        // Reload dates in case new dates appeared
        await loadDates();
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
    
    // No more frontend filtering — backend already filtered
    const filtered = allEvents;
    
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

// ---------- 批量分析 ----------

async function batchAnalyze() {
    const btn = document.getElementById("batch-analyze-btn");
    if (!selectedDate) {
        alert("请先选择一个日期");
        return;
    }

    btn.disabled = true;
    btn.textContent = "⚡ 启动中...";

    try {
        const res = await fetch("/api/batch-analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                date: selectedDate,
                platform: selectedPlatform
            })
        });

        if (res.status === 409) {
            alert("已有批量分析任务正在运行，请等待完成。");
            btn.disabled = false;
            btn.textContent = "⚡ 批量分析";
            return;
        }

        const data = await res.json();

        if (data.status === "empty") {
            alert("当前筛选条件下没有待分析或失败的事件。");
            btn.disabled = false;
            btn.textContent = "⚡ 批量分析";
            return;
        }

        // Show progress toast
        showBatchProgress(data.total);
        // Start polling
        startBatchPolling();

        if (data.original_total > data.limit) {
            alert(`提示：当前共有 ${data.original_total} 条待分析/失败的事件。\n由于并发和系统负载限制，本次批量分析仅处理前 ${data.limit} 条，剩余事件可在本次完成后再次发起。`);
        }

    } catch (e) {
        alert("启动批量分析失败，请检查后端服务。");
        btn.disabled = false;
        btn.textContent = "⚡ 批量分析";
    }
}

function showBatchProgress(total) {
    const toast = document.getElementById("batch-progress");
    toast.classList.remove("hide");
    document.getElementById("batch-progress-count").textContent = `0 / ${total}`;
    document.getElementById("batch-progress-fill").style.width = "0%";
    document.getElementById("batch-progress-detail").textContent = "";
}

function startBatchPolling() {
    if (batchPollTimer) clearInterval(batchPollTimer);

    batchPollTimer = setInterval(async () => {
        try {
            const res = await fetch("/api/batch-analyze/status");
            const data = await res.json();
            updateBatchProgress(data);

            if (!data.running) {
                clearInterval(batchPollTimer);
                batchPollTimer = null;
                onBatchComplete(data);
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 2000);
}

function updateBatchProgress(data) {
    const done = data.completed + data.failed;
    const total = data.total;
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;

    document.getElementById("batch-progress-count").textContent = `${done} / ${total}`;
    document.getElementById("batch-progress-fill").style.width = `${pct}%`;

    let detail = "";
    if (data.failed > 0) {
        detail = `⚠️ ${data.failed} 条分析失败`;
    }
    document.getElementById("batch-progress-detail").textContent = detail;
}

function onBatchComplete(data) {
    const btn = document.getElementById("batch-analyze-btn");
    btn.disabled = false;
    btn.textContent = "⚡ 批量分析";

    let msg = `✅ 批量分析完成！成功 ${data.completed} 条`;
    if (data.failed > 0) {
        msg += `，失败 ${data.failed} 条`;
        if (data.failed_titles.length > 0) {
            msg += `\n失败项: ${data.failed_titles.join("、")}`;
        }
    }

    // Hide progress after brief delay
    setTimeout(() => {
        document.getElementById("batch-progress").classList.add("hide");
    }, 3000);

    // Refresh events
    loadEvents();
}

// ---------- 日报生成 ----------

async function generateReport() {
    if (!selectedDate) {
        alert("请先选择一个日期");
        return;
    }

    const btn = document.getElementById("generate-report-btn");
    btn.disabled = true;
    btn.textContent = "📄 生成中...";

    try {
        const res = await fetch(`/api/report/${selectedDate}`, {
            method: "POST"
        });

        if (res.status === 404) {
            const data = await res.json();
            alert(data.detail || "没有符合条件的事件");
            return;
        }

        const data = await res.json();

        if (data.status === "success") {
            reportMarkdownCache = data.markdown;
            // Render HTML in modal
            document.getElementById("report-html-content").innerHTML = data.html;
            document.getElementById("report-modal").classList.remove("hide");
        } else {
            alert("日报生成失败");
        }
    } catch (e) {
        alert("日报生成请求失败，请检查后端服务。");
    } finally {
        btn.disabled = false;
        btn.textContent = "📄 生成日报";
    }
}

function downloadReport() {
    if (!reportMarkdownCache) return;
    const blob = new Blob([reportMarkdownCache], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedDate}-daily-report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function closeReportModal() {
    document.getElementById("report-modal").classList.add("hide");
}

// ---------- 详情 Modal ----------

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
