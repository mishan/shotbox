/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { Page } from 'playwright';

export interface Dressing
{
    /** Shown at once, and gone `hold` ms later unless another comes. */
    caption (text: string): Promise<void>;
    /** Out of this page, for a still. `dress()` again brings them back. */
    remove (): Promise<void>;
}

export function dress (page: Page, options?: { hold?: number }): Promise<Dressing>;
