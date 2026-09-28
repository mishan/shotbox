/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * dress.mjs -- a pointer and captions, for a recording of a page.
 *
 *     const dressing = await dress(page);
 *     await page.mouse.move(400, 300, { steps: 24 });
 *     await dressing.caption('Alt  Enter — zoom');
 *     await page.keyboard.press('Alt+Enter');
 *     ...
 *     await dressing.remove();       // before a still
 *
 * A browser does not record its own cursor, so a recording of a drag is a
 * layout rearranging itself for no reason. So is a chord nobody can see
 * pressed. This draws a dot that follows the mouse, shrinks while a button
 * is down, and a caption at the bottom that fades out on its own.
 *
 * Both are nodes in the page, marked `data-shotbox', above everything and
 * taking no events. They come back after a navigation or a reload, once
 * the new page has a body: a node appended to <html> while the parser is
 * still on its way to <body> does not survive the trip.
 */

/* In the page: its own function, so it is sent as source and not as a
   closure over anything here. */
const DRESS = (hold) =>
{
    if (window.__shotbox)
        return;

    const put = () =>
    {
        const dot = document.createElement('div');
        const cap = document.createElement('div');

        dot.dataset.shotbox = 'pointer';
        dot.style.cssText = [
            'position: fixed', 'z-index: 2147483647', 'pointer-events: none',
            'width: 14px', 'height: 14px', 'margin: -7px 0 0 -7px',
            'border-radius: 50%', 'background: rgba(32,32,32,0.75)',
            'border: 2px solid #ffffff',
            'box-shadow: 0 1px 4px rgba(0,0,0,0.4)',
            'transition: transform 80ms ease-out',
            'transform: scale(1)', 'left: -20px', 'top: -20px',
        ].join(';');

        cap.dataset.shotbox = 'caption';
        cap.style.cssText = [
            'position: fixed', 'z-index: 2147483647', 'pointer-events: none',
            'left: 50%', 'bottom: 48px', 'transform: translateX(-50%)',
            'padding: 8px 16px', 'border-radius: 10px',
            'font: 600 18px/1.2 system-ui, sans-serif', 'color: #ffffff',
            'background: rgba(24,24,32,0.85)',
            'box-shadow: 0 4px 16px rgba(0,0,0,0.3)',
            'opacity: 0', 'transition: opacity 200ms',
        ].join(';');

        document.body.append(dot, cap);

        addEventListener('mousemove', (e) =>
        {
            dot.style.left = `${e.clientX}px`;
            dot.style.top = `${e.clientY}px`;
        }, true);
        addEventListener('mousedown',
                         () => { dot.style.transform = 'scale(0.6)'; }, true);
        addEventListener('mouseup',
                         () => { dot.style.transform = 'scale(1)'; }, true);

        let fading = 0;

        window.__shotbox = {
            caption (text)
            {
                cap.textContent = text;
                cap.style.opacity = '1';
                clearTimeout(fading);
                fading = setTimeout(() => { cap.style.opacity = '0'; }, hold);
            },
            remove ()
            {
                dot.remove();
                cap.remove();
            },
        };
    };

    if (document.body)
        put();
    else
        addEventListener('DOMContentLoaded', put, { once: true });
};

export async function dress (page, { hold = 1300 } = {})
{
    await page.addInitScript(DRESS, hold);
    await page.evaluate(DRESS, hold);

    return {
        /* Shown at once, and gone `hold' ms later unless another comes. */
        caption: (text) => page.evaluate((t) => window.__shotbox?.caption(t),
                                         text),

        /* Out of this page, for a still of the page and not of the
           recording. A navigation after this brings them back. */
        remove: () => page.evaluate(() => window.__shotbox?.remove()),
    };
}
