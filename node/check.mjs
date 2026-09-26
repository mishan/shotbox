/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * check.mjs -- say what was checked, one line each, and count failures.
 *
 *     const t = checks();
 *     t.check(title === 'Home', 'the page has its title');
 *     t.skip('webkit has no moveBefore');
 *     process.exit(t.done());
 *
 * Lines start ok, FAIL or skip, so a run reads top to bottom and greps
 * well. `done' prints the tally and returns the failure count, which is
 * the exit status: zero only when nothing failed.
 */

export function checks (out = process.stdout)
{
    let passed = 0, failed = 0, skipped = 0;

    return {
        check (cond, what)
        {
            if (cond)
                passed++;
            else
                failed++;
            out.write(`${cond ? 'ok  ' : 'FAIL'}  ${what}\n`);
            return Boolean(cond);
        },

        /* A claim this run has no way to test, said rather than passed. */
        skip (what)
        {
            skipped++;
            out.write(`skip  ${what}\n`);
        },

        get failures () { return failed; },

        done ()
        {
            out.write(`\n${passed} ok, ${failed} failed, ${skipped} skipped\n`);
            return Math.min(failed, 125);
        },
    };
}
