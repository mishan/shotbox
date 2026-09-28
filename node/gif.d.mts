/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

export interface GifOptions
{
    /** Pixels wide; the height keeps the aspect. 1280. */
    width?: number;
    /** 12. */
    fps?: number;
    /** Seconds cut off the start of a video. 0. */
    from?: number;
    /** The palette's size, at most. 256. */
    colors?: number;
    /** ffmpeg's paletteuse dither: `none`, `bayer:bayer_scale=3` (the default), ... */
    dither?: string;
}

/** A recording -- a video, or a directory from `frames()` -- as a GIF,
 *  via ffmpeg; resolves to `out`. */
export function gif (film: string, out: string, options?: GifOptions): Promise<string>;
