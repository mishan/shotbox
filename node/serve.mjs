#!/usr/bin/env node
/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * serve.mjs -- files over HTTP, for a browser under test.
 *
 * Small on purpose. A module with no runtime dependencies should not
 * grow a development one to look at its own demo page, and everything
 * this has to do is answer GET with a file and the right type: ES
 * modules need `text/javascript' or a browser refuses to import them,
 * which is the whole reason `file://' will not do. Port 0 by default:
 * the system picks a free one, so two runs never collide.
 *
 * It serves this repository to this machine and is not a web server: no
 * listings, no ranges, no compression, and nothing here has been thought
 * about as though somebody hostile could reach it.
 */

import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'text/javascript; charset=utf-8',
    '.mjs':  'text/javascript; charset=utf-8',
    '.css':  'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg':  'image/svg+xml',
};

/* Resolves once the port is known: `listen' is asynchronous, so a server
   returned any earlier has `address()' of null and the caller finds out
   by dereferencing it. */
export function serve (root, port = 0, host = '127.0.0.1')
{
    root = path.resolve(root);

    const server = http.createServer((req, res) =>
    {
        const url = new URL(req.url, 'http://localhost');
        let asked = null;

        /* A percent escape that is not one. `decodeURIComponent' throws
           on it, and an exception out of a request handler is the whole
           process gone -- a development server that a stray address can
           stop is a test run that fails for no reason anybody can see. */
        try
        {
            asked = decodeURIComponent(url.pathname);
        }
        catch
        {
            res.writeHead(400).end('not a path');
            return;
        }

        /* A directory is its index.html, which is what a link ending in a
           slash means everywhere else and what `npm run demo' prints. */
        const file = path.join(root,
                               asked.endsWith('/') ? `${asked}index.html`
                                                   : asked);

        /* A path that climbs out of the root is not a path this answers,
           however it was spelled -- and the separator matters: `root' and
           `root-other' share a prefix and nothing else. */
        if (file !== root && !file.startsWith(root + path.sep))
        {
            res.writeHead(403).end('no');
            return;
        }

        fs.readFile(file, (err, body) =>
        {
            /* A directory asked for without the slash reads as EISDIR
               rather than as a missing file; both are the same answer
               here, since this serves what is there and does not make
               listings. */
            if (err)
            {
                res.writeHead(404).end('not here');
                return;
            }

            res.writeHead(200, {
                'Content-Type': TYPES[path.extname(file)] ??
                                'application/octet-stream',
                'Cache-Control': 'no-store',
            });
            res.end(body);
        });
    });

    return new Promise((ok, no) =>
    {
        server.once('error', no);
        server.listen(port, host, () => ok(server));
    });
}

/* `shotbox-serve [DIR] [PORT] [PATH]' to look at a directory by hand,
   saying where: PATH is the page to print the address of, for a
   directory whose page is not at its top. Compared by real path, since
   npm runs it through a link in node_modules/.bin, and the link's name
   is not this file's. */
if (process.argv[1] &&
    fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url))
{
    const [dir = '.', port = '8080', page = '/'] = process.argv.slice(2);
    const site = await serve(dir, Number(port));

    process.stdout.write(`http://127.0.0.1:${site.address().port}` +
                         `${page.startsWith('/') ? page : `/${page}`}\n`);
}
