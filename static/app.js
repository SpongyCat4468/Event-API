const REFRESH_MS = 3000;
const OVERLAY_MS = 5000;
const FEATURED_NEWS_MS = 30_000;
const BOOT_NEWS_OVERLAY_WINDOW_MS = 10 * 60_000;
const COLORS = {
  INFOR: "#37d6ff",
  CMIOC: "#ff4fc3",
  IZCC: "#ffd76a",
};

const tickerGrid = document.getElementById("tickerGrid");
const featuredNewsPanel = document.getElementById("featuredNewsPanel");
const featuredNewsMeta = document.getElementById("featuredNewsMeta");
const featuredNewsText = document.getElementById("featuredNewsText");
const frontPageOverlay = document.getElementById("frontPageOverlay");
const frontPageMeta = document.getElementById("frontPageMeta");
const frontPageHeadline = document.getElementById("frontPageHeadline");
const apiStatus = document.getElementById("apiStatus");
const connection = document.querySelector(".connection");
const serverTime = document.getElementById("serverTime");
const canvas = document.getElementById("priceChart");
const ctx = canvas.getContext("2d");

const priceFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

const compactPriceFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

const timeFormatter = new Intl.DateTimeFormat("zh-TW", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

let marketData = [];
let newsData = [];
let pollingTimer = null;
let seenNewsKey = null;
let hasLoadedOnce = false;
let overlayTimer = null;
let overlayExitTimer = null;
let featuredNewsTimer = null;

function applyBaseInlineStyles() {
  const title = document.querySelector("h1");
  const brandline = document.querySelector(".brandline");
  if (title) {
    Object.assign(title.style, {
      color: "#FFFFFF",
      fontSize: "clamp(2.1rem, 5vw, 4.6rem)",
      fontWeight: "850",
      lineHeight: "1.02",
      textShadow: "0 0 12px #38ff7e, 0 0 30px #123f22",
    });
  }
  if (brandline) {
    Object.assign(brandline.style, {
      color: "#FFFFFF",
      fontSize: "clamp(1rem, 1.4vw, 1.25rem)",
      fontWeight: "1000",
      marginTop: "14px",
    });
  }
}

function newsToneColor(item) {
  return Number(item.percent) > 0 ? "#FF4D4D" : "#00E676";
}

function applyFeaturedInlineStyles(item) {
  const toneColor = newsToneColor(item);
  const label = featuredNewsPanel.querySelector(".featured-news-label");
  const body = featuredNewsPanel.querySelector(".featured-news-body");
  Object.assign(featuredNewsPanel.style, {
    display: "grid",
    gridTemplateColumns: "auto minmax(0, 1fr)",
    alignItems: "stretch",
    margin: "18px clamp(18px, 4vw, 48px) 0",
    border: `7px solid ${toneColor}`,
    borderRadius: "8px",
    background: "#08180f",
    boxShadow: `inset 0 0 0 4px #FFFFFF, 0 0 0 3px #092414, 0 0 34px ${toneColor}`,
    color: "#FFFFFF",
    overflow: "hidden",
  });
  if (label) {
    Object.assign(label.style, {
      display: "grid",
      placeItems: "center",
      minWidth: "190px",
      padding: "16px 24px",
      borderRight: "5px solid #FFFFFF",
      background: toneColor,
      color: "#FFFFFF",
      fontSize: "clamp(1rem, 2vw, 1.7rem)",
      fontWeight: "1000",
    });
  }
  if (body) {
    Object.assign(body.style, {
      display: "grid",
      gap: "8px",
      minHeight: "104px",
      alignContent: "center",
      padding: "16px 24px",
    });
  }
  Object.assign(featuredNewsMeta.style, {
    color: "#ffd76a",
    fontWeight: "1000",
  });
  Object.assign(featuredNewsText.style, {
    color: "#FFFFFF",
    fontSize: "clamp(1.35rem, 2.8vw, 2.5rem)",
    fontWeight: "1000",
    lineHeight: "1.12",
  });
}

function applyOverlayInlineStyles(item) {
  const toneColor = newsToneColor(item);
  const paper = frontPageOverlay.querySelector(".frontpage-paper");
  const kicker = frontPageOverlay.querySelector(".frontpage-kicker");
  const title = frontPageOverlay.querySelector(".frontpage-title");
  Object.assign(frontPageOverlay.style, {
    position: "fixed",
    inset: "0",
    zIndex: "10000",
    display: "grid",
    placeItems: "center",
    padding: "clamp(18px, 4vw, 64px)",
    background: "#010302",
  });
  if (paper) {
    Object.assign(paper.style, {
      width: "min(1180px, 94vw)",
      minHeight: "min(720px, 84vh)",
      display: "grid",
      alignContent: "center",
      gap: "clamp(16px, 3vw, 34px)",
      padding: "clamp(24px, 5vw, 64px)",
      border: `10px solid ${toneColor}`,
      borderRadius: "8px",
      background: "#06120b",
      color: "#FFFFFF",
      boxShadow: `inset 0 0 0 5px #FFFFFF, 0 0 0 6px #0a2a17, 0 0 42px ${toneColor}`,
    });
  }
  if (kicker) {
    Object.assign(kicker.style, {
      width: "fit-content",
      padding: "10px 20px",
      border: "4px solid #FFFFFF",
      background: toneColor,
      color: "#FFFFFF",
      fontSize: "clamp(1rem, 2.4vw, 2rem)",
      fontWeight: "1000",
    });
  }
  if (title) {
    Object.assign(title.style, {
      borderTop: "6px solid #FFFFFF",
      borderBottom: "6px solid #FFFFFF",
      padding: "18px 0",
      color: "#FFFFFF",
      fontSize: "clamp(3rem, 8vw, 8rem)",
      fontWeight: "1000",
      lineHeight: "0.95",
    });
  }
  Object.assign(frontPageMeta.style, {
    color: toneColor,
    fontSize: "clamp(1.2rem, 2.6vw, 2.4rem)",
    fontWeight: "1000",
  });
  Object.assign(frontPageHeadline.style, {
    color: "#FFFFFF",
    fontSize: "clamp(2rem, 5.4vw, 5.8rem)",
    fontWeight: "1000",
    lineHeight: "1.06",
  });
}

function setConnection(status, text) {
  connection.classList.remove("online", "offline");
  connection.classList.add(status);
  apiStatus.textContent = text;
}

function createEl(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function renderTickers(prices) {
  tickerGrid.replaceChildren();

  for (const coin of prices) {
    const ticker = createEl("article", "ticker");
    const top = createEl("div", "ticker-top");
    const title = createEl("div");
    const symbol = createEl("div", "symbol", coin.symbol);
    const name = createEl("div", "coin-name", coin.name);
    const change = createEl(
      "div",
      `change ${coin.change_percent < 0 ? "down" : "up"}`,
      `${coin.change_percent >= 0 ? "+" : ""}${coin.change_percent.toFixed(2)}%`,
    );
    const price = createEl("div", "price", priceFormatter.format(coin.current_price));
    Object.assign(symbol.style, {
      fontSize: "clamp(1.55rem, 2.6vw, 2.15rem)",
      fontWeight: "1000",
    });

    title.append(symbol, name);
    top.append(title, change);
    ticker.append(top, price);
    ticker.style.borderColor = COLORS[coin.symbol] || "#0f6f3b";
    tickerGrid.append(ticker);
  }
}

function newsKey(item) {
  if (!item) return "";
  return `${item.created_at}|${item.headline}|${item.symbol || "market"}|${item.percent}`;
}

function formatNewsMeta(item) {
  return item.symbol || "市場快訊";
}

function showFeaturedNews(item) {
  featuredNewsPanel.hidden = false;
  featuredNewsPanel.classList.remove("is-empty");
  featuredNewsPanel.classList.add("is-active");
  applyFeaturedInlineStyles(item);
  featuredNewsMeta.textContent = formatNewsMeta(item);
  featuredNewsText.textContent = item.headline;

  window.clearTimeout(featuredNewsTimer);
  featuredNewsTimer = window.setTimeout(() => {
    featuredNewsPanel.classList.remove("is-active");
    featuredNewsPanel.classList.add("is-empty");
    featuredNewsMeta.textContent = "";
    featuredNewsText.textContent = "";
    featuredNewsPanel.hidden = true;
    featuredNewsPanel.removeAttribute("style");
  }, FEATURED_NEWS_MS);
}

function triggerFrontPage(item) {
  frontPageMeta.textContent = formatNewsMeta(item);
  frontPageHeadline.textContent = item.headline;
  frontPageOverlay.hidden = false;
  applyOverlayInlineStyles(item);
  frontPageOverlay.setAttribute("aria-hidden", "false");
  frontPageOverlay.classList.remove("is-exiting");
  frontPageOverlay.classList.add("is-active");

  window.clearTimeout(overlayTimer);
  window.clearTimeout(overlayExitTimer);
  window.clearTimeout(featuredNewsTimer);

  overlayTimer = window.setTimeout(() => {
    showFeaturedNews(item);
    frontPageOverlay.classList.add("is-exiting");
    overlayExitTimer = window.setTimeout(() => {
      frontPageOverlay.classList.remove("is-active", "is-exiting");
      frontPageOverlay.setAttribute("aria-hidden", "true");
      frontPageOverlay.hidden = true;
      frontPageOverlay.removeAttribute("style");
    }, 900);
  }, OVERLAY_MS);
}

function handleLatestNews(news) {
  const visibleNews = news.filter((item) => item && item.source !== "system");
  const latest = visibleNews[0];
  if (!latest) return;

  const key = newsKey(latest);
  if (!hasLoadedOnce) {
    seenNewsKey = key;
    hasLoadedOnce = true;

    const ageMs = Date.now() - new Date(latest.created_at).getTime();
    if (ageMs >= 0 && ageMs < BOOT_NEWS_OVERLAY_WINDOW_MS) {
      triggerFrontPage(latest);
    }
    return;
  }

  if (key && key !== seenNewsKey) {
    seenNewsKey = key;
    triggerFrontPage(latest);
  }
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(320, Math.floor(rect.width * ratio));
  canvas.height = Math.max(260, Math.floor(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  drawChart();
}

function drawChart() {
  const rect = canvas.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  ctx.clearRect(0, 0, width, height);

  const series = marketData
    .map((coin) => ({
      symbol: coin.symbol,
      name: coin.name,
      color: COLORS[coin.symbol] || "#38ff7e",
      points: coin.history.map((point) => ({
        time: new Date(point.recorded_at),
        price: Number(point.price),
      })),
    }))
    .filter((coin) => coin.points.length);

  const allPrices = series.flatMap((coin) => coin.points.map((point) => point.price));
  if (!allPrices.length) {
    ctx.fillStyle = "#FFFFFF";
    ctx.font = "900 16px sans-serif";
    ctx.fillText("等待市場資料", 24, 42);
    return;
  }

  const padding = { top: 28, right: 22, bottom: 42, left: 66 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  let min = Math.min(...allPrices);
  let max = Math.max(...allPrices);
  if (min === max) {
    if (max === 0) {
      max = 1;
    } else {
      min = Math.max(0, min * 0.96);
      max *= 1.04;
    }
  }
  const spread = max - min || 1;
  min = Math.max(0, min - spread * 0.08);
  max += spread * 0.08;

  ctx.strokeStyle = "#0f6f3b";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#FFFFFF";
  ctx.font = "900 12px sans-serif";
  ctx.textBaseline = "middle";

  for (let i = 0; i <= 5; i += 1) {
    const y = padding.top + (plotHeight / 5) * i;
    const value = max - ((max - min) / 5) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillText(compactPriceFormatter.format(value), 10, y);
  }

  for (let i = 0; i <= 5; i += 1) {
    const x = padding.left + (plotWidth / 5) * i;
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.stroke();
  }

  for (const coin of series) {
    ctx.strokeStyle = coin.color;
    ctx.lineWidth = 2.4;
    ctx.shadowColor = coin.color;
    ctx.shadowBlur = 10;
    ctx.beginPath();

    coin.points.forEach((point, index) => {
      const x = padding.left + (plotWidth * index) / Math.max(1, coin.points.length - 1);
      const y = padding.top + plotHeight - ((point.price - min) / (max - min)) * plotHeight;
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });

    ctx.stroke();
    ctx.shadowBlur = 0;

    const last = coin.points[coin.points.length - 1];
    const lastX = padding.left + plotWidth;
    const lastY = padding.top + plotHeight - ((last.price - min) / (max - min)) * plotHeight;
    ctx.fillStyle = coin.color;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fill();
  }

  let legendX = padding.left;
  ctx.font = "900 13px sans-serif";
  for (const coin of series) {
    ctx.fillStyle = coin.color;
    ctx.fillRect(legendX, height - 22, 16, 3);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(coin.symbol, legendX + 24, height - 20);
    legendX += 78;
  }
}

async function refreshPrices() {
  try {
    const response = await fetch("/price", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    marketData = data.prices || [];
    newsData = data.news || [];

    renderTickers(marketData);
    handleLatestNews(newsData);
    serverTime.textContent = timeFormatter.format(new Date(data.server_time));
    setConnection("online", "API 即時連線");
    drawChart();
  } catch (error) {
    setConnection("offline", "API 離線");
    featuredNewsPanel.hidden = false;
    featuredNewsPanel.classList.remove("is-empty");
    featuredNewsMeta.textContent = "API 離線";
    featuredNewsText.textContent = error.message;
  }
}

function boot() {
  applyBaseInlineStyles();
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();
  refreshPrices();
  pollingTimer = window.setInterval(refreshPrices, REFRESH_MS);
}

boot();
