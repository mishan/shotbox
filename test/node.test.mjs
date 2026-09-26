/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

import { checks, launch, serve, until } from '../node/index.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));

/* A request with the path exactly as written: fetch() tidies away the
   "../" a hostile client would send. */
const raw = (site, where) => new Promise((ok, no) =>
    http.get({ host: '127.0.0.1', port: site.address().port, path: where },
             (res) => { res.resume(); ok(res.statusCode); }).on('error', no));

test('serve answers with the file and its type, and nothing outside the root', async () =>
{
    const site = await serve(path.join(here, '..', 'node'));
    const base = `http://127.0.0.1:${site.address().port}`;

    try
    {
        const ok = await fetch(`${base}/index.mjs`);
        assert.equal(ok.status, 200);
        assert.match(ok.headers.get('content-type'), /text\/javascript/);
        assert.equal(await raw(site, '/..%2fREADME.md'), 403);
        assert.equal((await fetch(`${base}/%E0%A4%A`)).status, 400);
        assert.equal((await fetch(`${base}/nope.txt`)).status, 404);
    }
    finally
    {
        site.close();
    }
});

test('launch reports how a program ended and what it said', async () =>
{
    const a = launch('sh', ['-c', 'echo hello; exit 3']);
    assert.ok(await until(() => a.done, 5000));
    assert.match(a.why(0), /code 3/);
    assert.match(a.why(0), /hello/);

    const b = launch('shotbox-no-such-program');
    assert.ok(await until(() => b.done, 5000));
    assert.match(b.why(0), /could not be started/);
});

test('launch kills the whole group, children and all', async () =>
{
    const a = launch('sh', ['-c', 'sleep 30 & sleep 30; wait']);
    await new Promise((ok) => setTimeout(ok, 200));
    a.kill();
    assert.ok(await until(() => a.done, 5000));
});

test('checks count failures and say each one', () =>
{
    let said = '';
    const t = checks({ write: (s) => { said += s; } });

    t.check(true, 'one');
    t.check(false, 'two');
    t.skip('three');
    assert.equal(t.done(), 1);
    assert.match(said, /^ok {4}one$/m);
    assert.match(said, /^FAIL {2}two$/m);
    assert.match(said, /^skip {2}three$/m);
});
