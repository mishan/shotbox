/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

export interface SealOptions
{
    /** Names let through from this process's environment, as `--pass`. */
    pass?: readonly string[];
    /** Values set, as `--env`. */
    env?: Record<string, string>;
}

export interface Seal
{
    /** The scratch dir the home is in. */
    readonly dir: string;
    /** For `chromium.launch({ env })`. */
    readonly env: Record<string, string>;
    close (): Promise<void>;
}

export function sealed (options?: SealOptions): Promise<Seal>;
