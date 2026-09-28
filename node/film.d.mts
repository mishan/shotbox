/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { Page } from 'playwright';

export interface Reel
{
    /** The loop begins here: what came before is cut. */
    start (): void;
    /** Seconds from `film()` to `start()`, for `gif()`'s `from`. */
    readonly from: number;
    /** Closes the page's context and resolves to the video. */
    end (): Promise<string>;
}

/** Throws unless the page's context was made with `recordVideo`. */
export function film (page: Page): Reel;
