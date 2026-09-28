/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * sealed.mjs -- an environment for a browser that nothing of yours gets
 * into.
 *
 *     const seal = await sealed();
 *     const browser = await chromium.launch({ env: seal.env });
 *     ...
 *     await browser.close();
 *     await seal.close();
 *
 * A headless browser needs no display, but it still reads your home:
 * fontconfig takes ~/.config/fontconfig and ~/.local/share/fonts, so an
 * alias or a font you installed changes what the page is drawn with, and
 * a picture taken on your machine is not the one taken on anybody else's.
 * The same seal as a session's (session.py), without the display: the
 * environment rebuilt from an allowlist, HOME and every XDG directory in
 * a scratch dir, LANG and TZ fixed, and no DISPLAY, WAYLAND_DISPLAY or
 * session bus to reach your desktop through.
 *
 * Playwright finds its browsers from this process, not from the browser's
 * environment, so a scratch home does not hide them.
 */

import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

/* Passed through from the caller, as session.py's PASS: everything else
   is rebuilt. */
const PASS = ['PATH', 'USER', 'LOGNAME', 'SHELL', 'TERM'];

export async function sealed ({ pass = [], env = {} } = {})
{
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'shotbox-'));
    const home = path.join(dir, 'home');
    const run = path.join(dir, 'run');
    const xdg = {
        XDG_CONFIG_HOME: path.join(home, '.config'),
        XDG_DATA_HOME: path.join(home, '.local', 'share'),
        XDG_STATE_HOME: path.join(home, '.local', 'state'),
        XDG_CACHE_HOME: path.join(home, '.cache'),
    };

    for (const d of Object.values(xdg))
        await fs.mkdir(d, { recursive: true });
    await fs.mkdir(run, { mode: 0o700 });

    const kept = Object.fromEntries(
        [...PASS, ...pass].filter((k) => k in process.env)
                          .map((k) => [k, process.env[k]]));

    return {
        dir,
        env: {
            ...kept,
            LANG: 'C.UTF-8',
            TZ: 'UTC',
            HOME: home,
            ...xdg,
            XDG_RUNTIME_DIR: run,
            ...env,
        },
        close: () => fs.rm(dir, { recursive: true, force: true }),
    };
}
