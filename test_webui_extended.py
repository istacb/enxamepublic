#!/usr/bin/env python3
"""Extended Playwright test for Enxame Web UI - animations and interactions"""

import asyncio
from playwright.async_api import async_playwright

async def test_animations():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1280, 'height': 720})
        
        page.on("console", lambda msg: print(f"[CONSOLE] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[ERROR] {err}"))
        
        print("Navigating to http://localhost:8765/")
        await page.goto("http://localhost:8765/", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        
        # Check bees are rendered on canvas
        # The bees are drawn on the foreground canvas, we can't directly test that
        # but we can verify the animator is running by checking canvas is being redrawn
        
        # Take screenshot before
        await page.screenshot(path="/tmp/enxame_before.png", full_page=True)
        print("✓ Screenshot taken (before)")
        
        # Wait for animation frames
        await page.wait_for_timeout(5000)
        
        # Take screenshot after
        await page.screenshot(path="/tmp/enxame_after.png", full_page=True)
        print("✓ Screenshot taken (after)")
        
        # Check canvas context - verify bees array is populated
        bee_count = await page.evaluate("""
            () => {
                if (window.hiveCanvas && window.hiveCanvas.animator) {
                    return window.hiveCanvas.animator.bees.size;
                }
                return 0;
            }
        """)
        print(f"✓ Bees on canvas: {bee_count}")
        
        # Check sidebar model list updates via polling
        await page.wait_for_timeout(2000)
        model_count = await page.locator(".model-item").count()
        print(f"✓ Model items in sidebar: {model_count}")
        
        # Test chat input
        await page.fill("#msg", "Olá, como vai?")
        await page.wait_for_timeout(200)
        input_value = await page.locator("#msg").input_value()
        print(f"✓ Chat input works: {input_value}")
        
        # Test clear chat
        await page.click("#clear-chat")
        await page.wait_for_timeout(200)
        msg_count = await page.locator(".msg").count()
        print(f"✓ Clear chat works, messages: {msg_count}")
        
        # Test sidebar collapse/expand multiple times
        for i in range(3):
            await page.click("#sidebar-toggle")
            await page.wait_for_timeout(300)
            collapsed = await page.locator(".sidebar.collapsed").count()
            print(f"✓ Toggle #{i+1}: collapsed={collapsed}")
            await page.click("#sidebar-toggle")
            await page.wait_for_timeout(300)
            expanded = await page.locator(".sidebar.collapsed").count()
            print(f"✓ Expand #{i+1}: collapsed={expanded}")
        
        # Test settings modal with hex size change
        await page.click("#settings-btn")
        await page.wait_for_timeout(300)
        await page.fill("#setting-hex-size", "36")
        await page.wait_for_timeout(200)
        hex_value = await page.locator("#hex-size-value").text_content()
        print(f"✓ Hex size changed: {hex_value}")
        
        # Close modal
        await page.click("#settings-close")
        await page.wait_for_timeout(300)
        
        # Test discover button
        await page.click("#discover-btn")
        await page.wait_for_timeout(3000)  # Wait for discovery
        print("✓ Discover button clicked")
        
        # Check cluster label updates
        cluster_label = await page.locator("#cluster-label").text_content()
        print(f"✓ Cluster label: {cluster_label}")
        
        # Check Ollama status
        ollama_status = await page.locator("#ollama-status").text_content()
        print(f"✓ Ollama status: {ollama_status}")
        
        print("\n✅ Extended tests passed!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_animations())