/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * gif.mjs -- a recording (Playwright's recordVideo webm) as a GIF.
 *
 *     await gif(await page.video().path(), 'demo/demo.gif', { width: 1280 });
 *
 * Through a palette of its own: the default 216 colors turn a page of
 * flat grays into bands. Needs ffmpeg.
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

function run (cmd, args)
{
    return new Promise((ok, no) =>
    {
        const child = spawn(cmd, args, { stdio: ['ignore', 'ignore', 'pipe'] });
        let err = '';

        child.stderr.on('data', (d) => { err = (err + d).slice(-2000); });
        child.on('error', no);
        child.on('exit', (code) => code === 0 ? ok()
            : no(new Error(`${cmd} exited ${code}: ${err.trim()}`)));
    });
}

export async function gif (film, out, { width = 1280, fps = 12 } = {})
{
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'shotbox-gif-'));
    const palette = path.join(dir, 'palette.png');
    const filters = `fps=${fps},scale=${width}:-1:flags=lanczos`;

    try
    {
        await run('ffmpeg', ['-y', '-i', film, '-vf',
                             `${filters},palettegen=stats_mode=diff`, palette]);
        await run('ffmpeg', ['-y', '-i', film, '-i', palette, '-lavfi',
                             `${filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle`,
                             out]);
    }
    finally
    {
        await fs.rm(dir, { recursive: true, force: true });
    }
    return out;
}
