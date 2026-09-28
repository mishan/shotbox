/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * film.mjs -- where in a recording the part worth keeping starts.
 *
 *     const context = await browser.newContext({ recordVideo: { dir } });
 *     const page = await context.newPage();
 *     const reel = film(page);
 *     await page.goto(url);           // the load, a blank page: cut
 *     reel.start();
 *     ...                             // the loop
 *     await gif(await reel.end(), 'demo.gif', { from: reel.from });
 *
 * Playwright records from the moment the page is made, so a recording
 * begins with a blank page and a load, and the loop begins wherever the
 * script got to by then. `from' is that, in seconds, for gif(). Call
 * film() straight after newPage(): the clock starts there. The video
 * starts a little after, so the cut can land a few tenths of a second
 * into the loop; leave a beat after start() before anything that matters.
 * And a frame is written only when the page repaints, so a page that
 * holds still from start() on leaves nothing after the cut.
 *
 * `end' closes the page's context, since the video is only whole once
 * it has, and resolves to the file.
 */

export function film (page)
{
    const video = page.video();

    if (!video)
        throw new Error('film: the page is not being recorded; ' +
                        'make its context with recordVideo');

    const began = performance.now();
    let from = 0;

    return {
        start () { from = (performance.now() - began) / 1000; },
        get from () { return from; },

        async end ()
        {
            await page.context().close();
            return video.path();
        },
    };
}
