import fs from "node:fs";
import path from "node:path";
import { chromium } from "../frontend/node_modules/playwright/index.mjs";

const dist = path.resolve("dist");
const assets = path.join(dist, "assets");
if (!fs.existsSync(path.join(dist, "index.html"))) throw new Error("frontend/dist/index.html is missing");
const cssFile = fs.readdirSync(assets).find((name) => name.endsWith(".css"));
if (!cssFile) throw new Error("No built Vite CSS asset found");
const css = fs.readFileSync(path.join(assets, cssFile), "utf8");
const labels = ["Mouse", "Click", "Scroll", "Keyboard", "Blank Screen", "Recording", "File Transfer", "Clipboard", "Zoom", "Fullscreen", "Disconnect", "Workflows"];
const buttons = labels.map((label) => "<button type='button'>" + label + "</button>").join("");
const html = "<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1.0, maximum-scale=5.0, viewport-fit=cover'><style>" + css +
"*{box-sizing:border-box}html,body{margin:0;width:100%;max-width:100%;overflow-x:hidden}.recording-modal-backdrop{position:fixed;inset:0;z-index:10010;display:flex;align-items:center;justify-content:center;padding:12px;background:#07142688}.recording-modal{background:#fff;border:1px solid #dce5ef;border-radius:16px;padding:20px;width:min(760px,calc(100vw - 20px));max-height:85dvh;overflow:auto}.viewer{min-width:0;width:100%}.screen{width:100%;height:40dvh;background:#000}</style></head><body>" +
"<div class='layout'><aside class='sidebar'>Navigation</aside><main class='main'><button class='sidebar-toggle' type='button' onclick=\"document.querySelector('.layout').classList.toggle('sidebar-collapsed')\">Toggle sidebar</button><section class='content'><article class='viewer'><div class='screen'></div></article></section></main></div>" +
"<div class='mobile-action-dock'><div class='dock-grid open'>" + buttons + "</div><button class='dock-fab' aria-label='Open remote controls'>Open</button></div>" +
"<div class='recording-modal-backdrop'><section class='recording-modal recordings-manager' role='dialog' aria-modal='true' aria-labelledby='recordings-title'><h2 id='recordings-title'>Host Recordings</h2><p>Responsive recording manager test fixture</p><div class='recording-row'><div><b>session_layout.mp4</b><small>300 KB</small></div><button>Download</button><button>Delete</button></div></section></div></body></html>";

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  for (const viewport of [
    { width: 390, height: 844, name: "mobile-portrait" },
    { width: 844, height: 390, name: "mobile-landscape" },
    { width: 1440, height: 900, name: "desktop" },
  ]) {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.setContent(html, { waitUntil: "domcontentloaded" });
    await page.locator(".sidebar-toggle").evaluate((element) => element.click());
    const sidebarCollapsed = await page.locator(".layout").evaluate((element) => element.classList.contains("sidebar-collapsed"));
    if (!sidebarCollapsed) throw new Error(viewport.name + ": sidebar did not collapse");
    const result = await page.evaluate(() => {
      const dock = document.querySelector(".mobile-action-dock");
      const modal = document.querySelector(".recordings-manager");
      const visible = (element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0 &&
          rect.left >= -1 && rect.right <= window.innerWidth + 1 && rect.top >= -1 && rect.bottom <= window.innerHeight + 1;
      };
      const dockButtons = [...dock.querySelectorAll(".dock-grid button")];
      return {
        width: window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        horizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
        dockVisible: visible(dock),
        visibleDockButtons: dockButtons.filter(visible).length,
        dockButtonCount: dockButtons.length,
        modalVisible: visible(modal),
        sidebarCollapsed: document.querySelector(".layout").classList.contains("sidebar-collapsed"),
      };
    });
    if (result.horizontalOverflow) throw new Error(viewport.name + ": horizontal overflow " + JSON.stringify(result));
    if (!result.dockVisible || result.visibleDockButtons !== labels.length) throw new Error(viewport.name + ": dock clipped " + JSON.stringify(result));
    if (!result.modalVisible) throw new Error(viewport.name + ": recording modal clipped " + JSON.stringify(result));
    console.log(viewport.name + ": PASS " + JSON.stringify(result));
  }
} finally {
  await browser.close();
}
