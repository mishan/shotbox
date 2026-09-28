/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { Writable } from 'node:stream';

export interface Checks
{
    /** Prints `ok` or `FAIL` and the claim; returns whether it held. */
    check (cond: unknown, what: string): boolean;
    /** A claim this run has no way to test, said rather than passed. */
    skip (what: string): void;
    readonly failures: number;
    /** Prints the tally; the failure count, capped for an exit status. */
    done (): number;
}

export function checks (out?: Writable): Checks;
