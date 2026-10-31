/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/* `text` with the last digit of its first number one higher, carrying
   ("42.50" to "42.51", "1,299" to "1,300"), or one lower where a carry
   would add a digit ("9" to "8"), so the text keeps its length and maps
   onto the same characters of the page's text nodes; null with no
   number. A plain space doesn't join digits, as "3 400 items" are two
   numbers more often than one. It runs in the page, from its source, so it uses nothing
   outside itself. */
export function bumped(text)
{
    const m = /\d+(?:[.,:]\d+|['\u00a0\u2009\u202f]\d{3}(?!\d))*/.exec(text);

    if (!m)
        return null;
    const digits = [...m[0]];
    const last = digits.findLastIndex((c) => /\d/.test(c));
    const at = digits.findLastIndex((c) => /[0-8]/.test(c));

    if (at < 0)
        digits[last] = '8';
    else
    {
        digits[at] = String(Number(digits[at]) + 1);
        for (let i = at + 1; i < digits.length; i++)
            if (/\d/.test(digits[i]))
                digits[i] = '0';
    }
    return text.slice(0, m.index) + digits.join('') + text.slice(m.index + m[0].length);
}
