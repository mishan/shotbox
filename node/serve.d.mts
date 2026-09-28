/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import type { Server } from 'node:http';

/** Files under `root` over HTTP on localhost; resolves once it listens. */
export function serve (root: string, port?: number, host?: string): Promise<Server>;
