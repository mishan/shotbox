/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { Page } from 'playwright';

/** Every uncaught exception and console.error the page has, as they come. */
export function pageErrors (page: Page, into?: string[]): string[];
