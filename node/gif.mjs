/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * gif.mjs -- a recording (Playwright's recordVideo webm) as a GIF.
 *
 *     await gif(await page.video().path(), 'demo/demo.gif', { width: 1280 });
 *     await gif(framesDir, 'demo/demo.gif', { fps: 8 });   // from frames()
 *
 * Through a palette of its own: the default 216 colors turn a page of
 * flat grays into bands. Needs ffmpeg.
 *
 * `from' skips that many seconds of the start: a recording begins with
 * the page, and a blank page and a load are rarely what the loop is of.
 * `colors' caps the palette and `dither' is ffmpeg's paletteuse dither
 * (`none', `bayer:bayer_scale=3', `sierra2_4a'): a page of flat grays
 * with something animating on it can want few colors and no dither, since
 * a dither pattern over a moving region is noise the gif pays for every
 * frame.
 *
 * A directory is frames() output, 00000.png on, taken at `fps': each is
 * a frame of the gif, so nothing is dropped or doubled, and `from' does
 * not apply.
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

export async function gif (film, out, { width = 1280, fps = 12, from = 0,
                                        colors = 256,
                                        dither = 'bayer:bayer_scale=3' } = {})
{
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'shotbox-gif-'));
    const palette = path.join(dir, 'palette.png');
    const filters = `fps=${fps},scale=${width}:-1:flags=lanczos`;
    const input = (await fs.stat(film)).isDirectory()
        ? ['-framerate', String(fps), '-i', path.join(film, '%05d.png')]
        : ['-ss', String(from), '-i', film];

    try
    {
        await run('ffmpeg', ['-y', ...input, '-vf',
                             `${filters},palettegen=stats_mode=diff:max_colors=${colors}`,
                             palette]);
        await run('ffmpeg', ['-y', ...input, '-i', palette, '-lavfi',
                             `${filters} [x]; [x][1:v] paletteuse=dither=${dither}:diff_mode=rectangle`,
                             out]);
    }
    finally
    {
        await fs.rm(dir, { recursive: true, force: true });
    }
    return out;
}
