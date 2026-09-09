/* Browser checks: actual media playback; provider mocks are explicitly test-only. */
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.env.REST_TEST_URL || "http://localhost:3000";
const evidence = path.resolve(__dirname, "../docs/evidence");
const report = { checkedAt: new Date().toISOString(), actualAI: false, checks: [], audio: {}, errors: [] };
function pass(name, detail = "") { report.checks.push({ name, passed: true, detail }); console.log(`PASS ${name}${detail ? `: ${detail}` : ""}`); }
async function visible(page, selector) { await page.locator(selector).waitFor({ state: "visible" }); }
async function route(page, name) { await page.evaluate((routeName) => { location.hash = routeName; }, name); await visible(page, `#${name}`); }
async function fillCare(page) {
  await page.locator('input[name="environment"][value="집"]').check({ force: true });
  await page.locator("#situation").fill("오랜 작업을 마치고 머리가 복잡해요.");
  await page.locator('[data-need="긴장을 내려놓고 싶어요."]').click();
}
async function mockAPI(page, status, data) {
  await page.route("**/api/recommend", (route) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) }));
}

(async () => {
  await fs.mkdir(evidence, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.REST_BROWSER || "chrome", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
  const page = await context.newPage();
  page.on("pageerror", (error) => report.errors.push(error.message));
  try {
    await page.goto(BASE);
    await page.waitForLoadState("networkidle");
    assert.equal(await page.locator("#breathing-audio").evaluate((audio) => audio.paused), true);
    await page.locator('.home-content a[href="#about"]').click();
    await visible(page, "#about");
    await page.locator('.choice[href="#relax"]').click();
    await visible(page, "#relax");
    await page.goBack();
    await visible(page, "#about");
    pass("Home → About → Personal navigation and browser Back");

    for (const size of [{ name: "desktop", width: 1440, height: 900 }, { name: "mobile", width: 390, height: 844 }, { name: "tablet", width: 768, height: 1024 }, { name: "small-mobile", width: 320, height: 740 }]) {
      await page.setViewportSize({ width: size.width, height: size.height });
      for (const name of ["home", "about", "relax", "care", "breathe"]) {
        await route(page, name);
        await page.waitForTimeout(120);
        const dimensions = await page.evaluate(() => ({ page: document.documentElement.scrollWidth, viewport: innerWidth }));
        assert.ok(dimensions.page <= dimensions.viewport, `${size.name}/${name}: horizontal overflow`);
        if (size.name !== "small-mobile") await page.screenshot({ path: path.join(evidence, `${size.name}-${name}.png`), fullPage: true });
      }
      pass(`Layout ${size.width}×${size.height}`, "5 screens; no horizontal overflow");
    }
    await page.setViewportSize({ width: 390, height: 844 });
    await route(page, "care");
    let apiRequests = 0;
    page.on("request", (request) => { if (request.url().endsWith("/api/recommend")) apiRequests++; });
    await page.locator("#recommend-button").click();
    assert.match(await page.locator("#care-status").innerText(), /조금만 더/);
    assert.equal(apiRequests, 0);
    pass("Empty input prevents API request");
    await fillCare(page);
    await page.screenshot({ path: path.join(evidence, "mobile-care-input.png"), fullPage: true });
    await page.locator("#recommend-button").click();
    await page.waitForFunction(() => document.querySelector("#care-status").textContent.includes("연결을 준비"));
    assert.equal(await page.locator("#recommend-button").isEnabled(), true);
    assert.equal(await page.locator("#care-result").isVisible(), false);
    await page.screenshot({ path: path.join(evidence, "mobile-api-not-configured.png"), fullPage: true });
    pass("Actual local API: missing key gives safe notice and retry, no fake result");

    for (const [status, response] of [[500, { error: { code: "INTERNAL_ERROR" } }], [429, { error: { code: "AI_RATE_LIMIT" } }], [200, { course_id: "invented", course: "bad", reason: "bad" }], [200, { course_id: "focus", course: "기본 집중 호흡", reason: "" }]]) {
      await mockAPI(page, status, response);
      await page.locator("#recommend-button").click();
      await page.waitForFunction(() => document.querySelector("#care-status").textContent.includes("연결이 고요"));
      assert.equal(await page.locator("#care-result").isVisible(), false);
      assert.equal(await page.locator("#recommend-button").isEnabled(), true);
      await page.unroute("**/api/recommend");
    }
    pass("UI test-only fixtures: HTTP 500/429 and invalid recommendations rejected");
    await page.clock.install();
    await page.route("**/api/recommend", () => {});
    await page.locator("#recommend-button").click();
    assert.equal(await page.locator("#recommend-button").isDisabled(), true);
    assert.match(await page.locator("#care-status").innerText(), /찾고 있어요/);
    await page.clock.fastForward(26000);
    await page.waitForFunction(() => document.querySelector("#care-status").textContent.includes("시간이 조금"));
    assert.equal(await page.locator("#recommend-button").isEnabled(), true);
    await page.unroute("**/api/recommend");
    pass("UI test-only clock: loading, duplicate-click prevention and 25s timeout");
    await mockAPI(page, 200, { course_id: "sleep", course: "편안한 수면 호흡", reason: "테스트용 모의 응답입니다. 실제 AI 추천이 아닙니다." });
    await page.locator("#recommend-button").click();
    await visible(page, "#care-result");
    assert.match(await page.locator("#result-title").innerText(), /편안한 수면 호흡/);
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await page.screenshot({ path: path.join(evidence, "mobile-result-TEST-ONLY.png"), fullPage: true });
    await page.locator("#accept-recommendation").click();
    await visible(page, "#relax");
    assert.equal(await page.locator('input[name="course"][value="sleep"]').isChecked(), true);
    assert.equal(await page.locator("#breathing-audio").evaluate((audio) => audio.paused), true);
    await page.unroute("**/api/recommend");
    pass("UI test-only fixture: recommendation selects matching course without autoplay");

    // New page with a real clock for actual local MP3 playback.
    await page.close();
    const player = await context.newPage();
    player.on("pageerror", (error) => report.errors.push(error.message));
    await player.goto(BASE);
    for (const id of ["focus", "sleep", "relax"]) {
      await route(player, "relax");
      await player.locator(`input[name="course"][value="${id}"]`).check({ force: true });
      await player.locator("#open-player").click();
      await visible(player, "#breathe");
      assert.equal(await player.locator("#breathing-audio").evaluate((audio) => audio.paused), true);
      await player.locator("#toggle-play").click();
      await player.waitForFunction(() => { const audio = document.querySelector("#breathing-audio"); return !audio.paused && audio.currentTime > 0.5; });
      report.audio[id] = await player.locator("#breathing-audio").evaluate((audio) => ({ source: audio.getAttribute("src"), duration: audio.duration, readyState: audio.readyState, currentTime: audio.currentTime }));
      assert.ok(report.audio[id].duration > 0);
      await player.waitForTimeout(650);
      await player.locator("#toggle-play").click();
      const elapsed = await player.locator("#elapsed").innerText();
      await player.waitForTimeout(1100);
      assert.equal(await player.locator("#elapsed").innerText(), elapsed);
      await player.locator("#toggle-play").click();
      await player.waitForFunction(() => !document.querySelector("#breathing-audio").paused);
      await route(player, "relax");
      assert.equal(await player.locator("#breathing-audio").evaluate((audio) => audio.paused), true);
      pass(`Real MP3 ${id}`, `play, pause, resume, stop on navigation; ${report.audio[id].duration.toFixed(2)}s source`);
    }
    await player.locator("#open-player").click();
    await visible(player, "#breathe");
    await player.locator("#mute-audio").click();
    assert.equal(await player.locator("#breathing-audio").evaluate((audio) => audio.muted), true);
    await player.locator("#volume").fill("30");
    assert.equal(await player.locator("#volume-value").innerText(), "30%");
    assert.equal(await player.locator("#breathing-audio").evaluate((audio) => audio.muted), false);
    await player.locator("#restart-session").click();
    await player.waitForFunction(() => !document.querySelector("#breathing-audio").paused);
    pass("Mute, volume, and restart from beginning");
    if (process.argv.includes("--full-duration")) {
      console.log("Running an actual 180-second session. No accelerated clock.");
      const started = Date.now();
      for (let interval = 1; interval <= 6; interval++) {
        await player.waitForTimeout(30000);
        console.log(`REAL TIMER ${interval * 30}s: ${await player.locator("#elapsed").innerText()}`);
      }
      await visible(player, "#completion");
      assert.equal(await player.locator("#elapsed").innerText(), "03:00");
      assert.equal(await player.locator("#breathing-audio").evaluate((audio) => audio.paused), true);
      assert.equal(await player.locator("#toggle-play").isDisabled(), true);
      await player.screenshot({ path: path.join(evidence, "desktop-completion-real-180s.png"), fullPage: true });
      pass("Actual 3-minute timer", `${Date.now() - started}ms wall time; completion, music stopped, controls disabled`);
      await player.locator("#repeat-session").click();
      await player.waitForFunction(() => !document.querySelector("#breathing-audio").paused);
      assert.equal(await player.locator("#completion").isVisible(), false);
      await route(player, "home");
      assert.equal(await player.locator("#breathing-audio").evaluate((audio) => audio.paused), true);
      pass("Completion → repeat → Home stops playback");
    } else {
      await route(player, "home");
    }
    assert.deepEqual(report.errors, []);
    pass("No uncaught browser JavaScript errors");
    report.status = "passed";
  } catch (error) {
    report.status = "failed";
    report.errors.push(error.stack);
    console.error(error);
    process.exitCode = 1;
  } finally {
    await browser.close();
    const reportName = process.argv.includes("--full-duration") ? "browser-report.json" : "browser-smoke-report.json";
    await fs.writeFile(path.join(evidence, reportName), JSON.stringify(report, null, 2));
  }
})();
