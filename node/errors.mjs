/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * errors.mjs -- everything a page threw or logged as an error.
 *
 *     const errors = pageErrors(page);
 *     ...
 *     t.check(errors.length === 0, `no page errors ${errors.join('; ')}`);
 *
 * Uncaught exceptions and console.error both count: a page that logs an
 * error and carries on has still gone wrong, and a check that only looks
 * at the DOM would pass it.
 */

export function pageErrors (page, into = [])
{
    page.on('pageerror', (e) => into.push(e.message));
    page.on('console', (m) =>
    {
        if (m.type() === 'error')
            into.push(m.text());
    });
    return into;
}
