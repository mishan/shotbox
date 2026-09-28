/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * The helpers that need a browser, in one: Playwright's Chromium, if it is
 * installed (`npm install && npx playwright install chromium`). Without it
 * they skip, saying so.
 */

import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { after, before, test } from 'node:test';

import { dress, film, gif, pageErrors, sealed } from '../node/index.mjs';

let chromium = null, why = false;

try
{
    ({ chromium } = await import('playwright'));
    await fs.access(chromium.executablePath());
}
catch (e)
{
    why = `no Playwright Chromium (${e.message.split('\n')[0]})`;
}

const has = (cmd) =>
{
    try { execFileSync(cmd, ['-version'], { stdio: 'ignore' }); return true; }
    catch { return false; }
};

let seal, browser;

before(async () =>
{
    if (why)
        return;
    seal = await sealed();
    browser = await chromium.launch({ env: seal.env });
});

after(async () =>
{
    await browser?.close();
    await seal?.close();
});

const PAGE = 'data:text/html,<body style="margin:0;height:100vh"></body>';

test('dress draws a pointer that follows the mouse', { skip: why }, async () =>
{
    const page = await browser.newPage();

    try
    {
        await page.goto(PAGE);
        await dress(page);

        const pointer = page.locator('[data-shotbox=pointer]');

        await page.mouse.move(120, 80);
        assert.deepEqual(await pointer.evaluate((n) => [n.style.left, n.style.top]),
                         ['120px', '80px']);

        await page.mouse.down();
        assert.match(await pointer.evaluate((n) => n.style.transform), /0\.6/);
        await page.mouse.up();

        /* And it takes no events: a click lands on what is under it. */
        assert.equal(await page.evaluate(() =>
            document.elementFromPoint(120, 80).dataset.shotbox), undefined);

        /* Back after a reload, once there is a body to put it in. */
        await page.reload();
        assert.equal(await page.locator('[data-shotbox]').count(), 2);
    }
    finally
    {
        await page.close();
    }
});

test('dress captions fade on their own, and remove takes it all out',
     { skip: why }, async () =>
{
    const page = await browser.newPage();

    try
    {
        await page.goto(PAGE);

        const dressing = await dress(page, { hold: 200 });
        const shown = () => page.locator('[data-shotbox=caption]').evaluate(
            (n) => [n.textContent, n.style.opacity]);

        await dressing.caption('Alt  Enter');
        assert.deepEqual(await shown(), ['Alt  Enter', '1']);
        await page.waitForTimeout(400);
        assert.deepEqual(await shown(), ['Alt  Enter', '0']);

        await dressing.remove();
        assert.equal(await page.locator('[data-shotbox]').count(), 0);
    }
    finally
    {
        await page.close();
    }
});

test('pageErrors hears both a throw and a console.error', { skip: why }, async () =>
{
    const page = await browser.newPage();

    try
    {
        const errors = pageErrors(page);

        await page.goto(PAGE);
        await page.evaluate(() =>
        {
            console.error('said');
            setTimeout(() => { throw new Error('thrown'); });
        });
        await page.waitForTimeout(100);
        assert.equal(errors.length, 2, errors.join(' | '));
    }
    finally
    {
        await page.close();
    }
});

test('film says where the loop starts, and gif cuts there',
     { skip: why || (!has('ffmpeg') && 'no ffmpeg') }, async () =>
{
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'shotbox-test-'));
    const plain = await browser.newPage();

    try
    {
        assert.throws(() => film(plain), /not being recorded/);

        const context = await browser.newContext({
            viewport: { width: 160, height: 120 },
            recordVideo: { dir, size: { width: 160, height: 120 } },
        });
        const page = await context.newPage();
        const reel = film(page);

        /* Red for the part to cut, blue from the start of the loop. And
           something moving in the corner: Playwright writes a frame only
           when the page repaints, so a page that holds still leaves
           nothing after the cut. */
        await page.goto(PAGE);
        await page.evaluate(() =>
        {
            const tick = document.body.appendChild(document.createElement('i'));
            const on = () => { tick.textContent = performance.now(); requestAnimationFrame(on); };

            on();
            document.body.style.background = '#ff0000';
        });
        await page.waitForTimeout(1500);
        await page.evaluate(() => { document.body.style.background = '#0000ff'; });
        await page.waitForTimeout(100);
        reel.start();
        await page.waitForTimeout(1500);

        assert.ok(reel.from > 1.4, `from ${reel.from}`);

        const video = await reel.end();
        const first = async (name, from) =>
        {
            const out = await gif(video, path.join(dir, name),
                                  { width: 160, fps: 10, from });
            const px = execFileSync('convert', [`${out}[0]`, '-format',
                                                '%[fx:int(255*p{80,60}.r)],%[fx:int(255*p{80,60}.b)]',
                                                'info:']).toString();
            const [r, b] = px.split(',').map(Number);

            return r > 200 && b < 60 ? 'red' : r < 60 && b > 200 ? 'blue' : px;
        };

        /* Uncut, it starts before the loop; cut, at it. */
        assert.notEqual(await first('all.gif', 0), 'blue');
        assert.equal(await first('loop.gif', reel.from), 'blue');
    }
    finally
    {
        await plain.close();
        await fs.rm(dir, { recursive: true, force: true });
    }
});
