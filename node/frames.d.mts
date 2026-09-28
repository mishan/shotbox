/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { Page } from 'playwright';

/** Chromium's flags for frames that come out the same: `launch({ args })`. */
export const steady: readonly string[];

export interface FramesOptions
{
    /** Where the frames go, as 00000.png on. */
    dir: string;
    /** 10. */
    fps?: number;
    /** What the page's Date says when it starts. 2026-01-01T00:00:00Z. */
    epoch?: string | number | Date;
    /** Math.random's seed. */
    seed?: number;
    /** Real-time ms let pass after a frame navigates, for it to paint. 150. */
    paint?: number;
}

export interface Recorder
{
    /** Milliseconds of page time so far. */
    readonly time: number;
    /** Frames kept so far. */
    readonly count: number;
    /** Page time passes, and nothing is kept. */
    run (ms: number): Promise<void>;
    /** From here, each frame is kept. */
    start (): void;
    /** A frame at a time for `ms` of page time: for `waitForTimeout`. */
    hold (ms: number): Promise<void>;
    /** The pointer to x, y over `ms`, a step a frame: for `mouse.move`. */
    move (x: number, y: number, ms?: number): Promise<void>;
    /** No more frames. */
    end (): Promise<{ dir: string; count: number; fps: number }>;
}

/** Call before the page's first navigation: its clock stands still from there. */
export function frames (page: Page, options: FramesOptions): Promise<Recorder>;
