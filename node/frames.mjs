/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * frames.mjs -- a recording made a frame at a time, the same each run.
 *
 *     const browser = await chromium.launch({ args: steady });
 *     const page = await browser.newPage();
 *     const rec = await frames(page, { fps: 8, dir });   // before goto
 *     await page.goto(url);
 *     await rec.run(1500);            // page time passes, nothing kept
 *     await rec.start();
 *     await rec.hold(600);            // for waitForTimeout
 *     await rec.move(400, 300, 500);  // for mouse.move({ steps })
 *     await page.mouse.down();        // input lands between frames
 *     ...
 *     await gif((await rec.end()).dir, 'demo.gif', { fps: 8 });
 *
 * A recording in real time is a different film each run: the page and
 * the recorder race, and the frames land wherever they land. Here the
 * page's time stands still, and moves one frame's worth between
 * screenshots. The count of frames is the length of the script in page
 * time, and each frame is the page at that moment.
 *
 * What is stood still:
 *
 * - page.clock, installed and paused before the page's first script:
 *   timers, Date, performance.now and requestAnimationFrame. Paused any
 *   later, real time has already leaked in. It is the context's clock,
 *   so every page in the context shares it.
 * - Web Animations -- CSS transitions and animations, element.animate --
 *   which page.clock does not reach. Each is paused when first seen and
 *   set to the page's time before every frame, in every frame.
 * - Math.random, seeded, which page.clock leaves alone.
 * - Chromium, with `steady': sRGB, no hinting, no GPU, no LCD text, and
 *   animations on the main thread, whose absence let the first frames
 *   race.
 *
 * What is not: anything real-time that is not a timer. A frame (re)loads,
 * a fetch returns, a worker answers, a picture decodes, each in its own
 * time. After a frame navigates, the recorder waits for it to load and
 * paint before time moves on, which covers an iframe rebuilt by the
 * page; the rest is the page's to make deterministic. WebGL and video
 * are not pinned.
 *
 * Near enough, not byte for byte: runs give the same number of frames
 * and the same frames, give or take a few pixels one level apart, so a
 * check should compare with a little fuzz.
 */

import fs from 'node:fs/promises';
import path from 'node:path';

/* For chromium.launch({ args }). */
export const steady = [
    '--force-color-profile=srgb',
    '--font-render-hinting=none',
    '--disable-gpu',
    '--disable-lcd-text',
    '--disable-threaded-animation',
];

/* In each frame, before each picture: every animation paused when first
   seen, and set to where the page's time has it. */
const PIN = (now) =>
{
    const born = (window.__shotboxBorn ??= new WeakMap());

    for (const a of document.getAnimations())
    {
        if (!born.has(a))
        {
            born.set(a, now);
            a.pause();
        }
        a.currentTime = (now - born.get(a)) * a.playbackRate;
    }
};

/* mulberry32: small, and the same numbers everywhere. */
const SEED = (seed) =>
{
    let a = seed | 0;

    Math.random = () =>
    {
        a = (a + 0x6d2b79f5) | 0;

        let t = Math.imul(a ^ (a >>> 15), 1 | a);

        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
};

export async function frames (page, { fps = 10, dir,
                                      epoch = '2026-01-01T00:00:00Z',
                                      seed = 0x5eed, paint = 150 } = {})
{
    if (!dir)
        throw new Error('frames: say where the frames go (dir)');

    const step = 1000 / fps;
    const t0 = new Date(epoch).getTime();
    let now = 0, count = 0, keeping = false, navigated = false;
    let mouse = { x: 0, y: 0 };

    /* Every document from here, and the one there already, which is
       what setContent() writes into. */
    await page.addInitScript(SEED, seed);
    await page.evaluate(SEED, seed);
    await page.clock.install({ time: t0 });
    await page.clock.pauseAt(t0);
    await fs.mkdir(dir, { recursive: true });

    page.on('framenavigated', () => { navigated = true; });
    page.on('frameattached', () => { navigated = true; });

    /* A frame that navigated loads in real time, not the page's: it is
       let load and paint before the page's time moves on, or a frame
       catches it blank one run and drawn the next. Only then: waiting in
       real time otherwise lets what else is real-time drift apart. */
    const settle = async () =>
    {
        while (navigated)
        {
            navigated = false;
            await Promise.all(page.frames().map(
                (f) => f.waitForLoadState('load').catch(() => {})));
            await page.waitForTimeout(paint);
        }
    };

    const pin = () => Promise.all(page.frames().map(
        (f) => f.evaluate(PIN, now).catch(() => {})));

    const frame = async () =>
    {
        if (keeping)
        {
            await pin();
            await page.screenshot({
                path: path.join(dir, `${String(count++).padStart(5, '0')}.png`),
            });
        }
        await settle();
        await page.clock.runFor(step);
        now += step;
        await pin();
    };

    const frameful = (ms) => Math.max(1, Math.round(ms / step));

    return {
        /* Milliseconds of page time so far. */
        get time () { return now; },
        get count () { return count; },

        /* Page time passes, nothing kept: a load, a settling. */
        async run (ms)
        {
            for (let i = Math.round(ms / step); i > 0; i--)
                await frame();
        },

        /* From here, each frame is kept. */
        start () { keeping = true; },

        /* A frame at a time for `ms' of page time. */
        async hold (ms)
        {
            for (let i = frameful(ms); i > 0; i--)
                await frame();
        },

        /* The pointer to x, y over `ms', a step each frame: moved all at
           once between two frames, a glide would be a jump. */
        async move (x, y, ms = 300)
        {
            const from = mouse;
            const n = frameful(ms);

            for (let i = 1; i <= n; i++)
            {
                mouse = { x: from.x + (x - from.x) * i / n,
                          y: from.y + (y - from.y) * i / n };
                await page.mouse.move(mouse.x, mouse.y);
                await frame();
            }
        },

        /* No more frames; where they are, how many, and at what rate. */
        async end ()
        {
            keeping = false;
            return { dir, count, fps };
        },
    };
}
