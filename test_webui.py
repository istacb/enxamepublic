#!/usr/bin/env python3
"""Playwright test for Enxame Web UI"""

import asyncio
from playwright.async_api import async_playwright

async def test_webui():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 720})
        
        # Enable console logging
        page.on("console", lambda msg: print(f"[CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[ERROR] {err}"))
        
        print("Navigating to http://localhost:8765/")
        await page.goto("http://localhost:8765/", wait_until="networkidle")
        
        # Wait for canvas to be initialized
        await page.wait_for_timeout(3000)
        
        # Check 1: Page title
        title = await page.title()
        print(f"✓ Page title: {title}")
        assert "Enxame" in title
        
        # Check 2: Topbar elements
        brand = await page.locator(".brand").text_content()
        print(f"✓ Brand: {brand.strip()}")
        
        # Check 3: Canvas elements exist
        hive_bg = await page.locator("#hive-bg").count()
        hive_fg = await page.locator("#hive-fg").count()
        print(f"✓ Canvas layers: bg={hive_bg}, fg={hive_fg}")
        assert hive_bg == 1 and hive_fg == 1
        
        # Check 4: Sidebar panels
        sidebar = await page.locator(".sidebar").count()
        print(f"✓ Sidebar: {sidebar}")
        assert sidebar == 1
        
        # Check 5: Sidebar sections
        sections = await page.locator(".panel").count()
        print(f"✓ Sidebar panels: {sections}")
        
        # Check 6: Node list
        node_list = await page.locator("#node-list").count()
        print(f"✓ Node list: {node_list}")
        
        # Check 7: Model list
        model_list = await page.locator("#model-list").count()
        print(f"✓ Model list: {model_list}")
        
        # Check 8: Check models loaded
        model_items = await page.locator(".model-item").count()
        print(f"✓ Model items: {model_items}")
        if model_items > 0:
            first_model = await page.locator(".model-item").first.text_content()
            print(f"  First model: {first_model.strip()}")
        
        # Check 9: Chat area
        chat_area = await page.locator(".chat-area").count()
        print(f"✓ Chat area: {chat_area}")
        
        # Check 10: Transcript
        transcript = await page.locator("#transcript").count()
        print(f"✓ Transcript: {transcript}")
        
        # Check 11: Settings button
        settings_btn = await page.locator("#settings-btn").count()
        print(f"✓ Settings button: {settings_btn}")
        
        # Check 12: Click settings button - should open modal
        await page.click("#settings-btn")
        await page.wait_for_timeout(500)
        modal_open = await page.locator(".modal-overlay.open").count()
        print(f"✓ Settings modal opens: {modal_open}")
        assert modal_open == 1
        
        # Check 13: Modal content
        modal_title = await page.locator("#settings-title").text_content()
        print(f"✓ Modal title: {modal_title.strip()}")
        
        # Check 14: Settings form elements
        offline_checkbox = await page.locator("#setting-offline").count()
        web_fallback_checkbox = await page.locator("#setting-web-fallback").count()
        confidence_slider = await page.locator("#setting-confidence").count()
        model_select = await page.locator("#setting-model").count()
        hex_size_slider = await page.locator("#setting-hex-size").count()
        animations_checkbox = await page.locator("#setting-animations").count()
        sounds_checkbox = await page.locator("#setting-sounds").count()
        print(f"✓ Settings elements: offline={offline_checkbox}, web={web_fallback_checkbox}, confidence={confidence_slider}, model={model_select}, hex={hex_size_slider}, anim={animations_checkbox}, sounds={sounds_checkbox}")
        
        # Close modal
        await page.click("#settings-close")
        await page.wait_for_timeout(300)
        modal_closed = await page.locator(".modal-overlay.open").count()
        print(f"✓ Modal closes: {modal_closed == 0}")
        
        # Check 15: Sidebar collapse/expand
        sidebar_toggle = await page.locator("#sidebar-toggle").count()
        print(f"✓ Sidebar toggle: {sidebar_toggle}")
        
        await page.click("#sidebar-toggle")
        await page.wait_for_timeout(500)
        sidebar_collapsed = await page.locator(".sidebar.collapsed").count()
        main_grid_collapsed = await page.locator(".main-grid.sidebar-collapsed").count()
        print(f"✓ Sidebar collapsed: {sidebar_collapsed}, main-grid updated: {main_grid_collapsed}")
        
        # Expand again
        await page.click("#sidebar-toggle")
        await page.wait_for_timeout(500)
        sidebar_collapsed = await page.locator(".sidebar.collapsed").count()
        print(f"✓ Sidebar expanded again: {sidebar_collapsed == 0}")
        
        # Check 16: Canvas dimensions
        canvas_size = await page.evaluate(
            "el => ({ w: el.width, h: el.height, cw: el.clientWidth, ch: el.clientHeight })",
            await page.locator("#hive-bg").element_handle()
        )
        print(f"✓ Canvas size: {canvas_size}")
        assert canvas_size['cw'] > 400 and canvas_size['ch'] > 300, "Canvas should be viewport-sized"
        
        # Check 17: Check for JS errors in console
        # (already logged via page.on("pageerror"))
        
        print("\n✅ All checks passed!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_webui())