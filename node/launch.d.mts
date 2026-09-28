/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { ChildProcess } from 'node:child_process';

export interface Launched
{
    child: ChildProcess;
    readonly done: boolean;
    /** The tail of what it printed, both streams. */
    readonly output: string;
    /** Kills its whole process group. */
    kill (): void;
    /** How it ended, or that it hadn't, and what it printed. */
    why (waited: number): string;
}

export interface LaunchOptions
{
    env?: NodeJS.ProcessEnv;
    /** Characters of output kept. 4000. */
    keep?: number;
}

export function launch (command: string, args?: readonly string[],
                        options?: LaunchOptions): Launched;

/** Polls `test` until it's true or `ms` pass; whether it came true. */
export function until (test: () => unknown, ms?: number, every?: number): Promise<boolean>;
