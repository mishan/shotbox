/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * launch.mjs -- start a program you mean to stop, and say why when it
 * didn't do what you waited for.
 *
 *     const app = launch('firefox', ['--profile', dir, url]);
 *     if (!await until(() => reported, 20000))
 *         throw new Error(app.why(20000));
 *     app.kill();
 *
 * `detached' puts the child in its own process group, which is the only
 * way to stop it cleanly: when what's spawned is a wrapper script (xvfb-run,
 * a browser's launcher), signalling it leaves its children running, and
 * those survivors hold the pipes open, so node sits there forever with
 * nothing left to do. Signalling the group reaches all of them.
 *
 * Output is kept, bounded: a program failing in a loop can print
 * megabytes, and the tail is the part that says why.
 */

import { spawn } from 'node:child_process';

export function launch (command, args = [], { env = process.env, keep = 4000 } = {})
{
    const child = spawn(command, args, {
        stdio: ['ignore', 'pipe', 'pipe'], env, detached: true,
    });
    const state = { done: false, code: null, signal: null, error: null, output: '' };
    const hold = (chunk) => { state.output = (state.output + chunk).slice(-keep); };

    child.stdout.setEncoding('utf8');
    child.stdout.on('data', hold);
    child.stderr.setEncoding('utf8');
    child.stderr.on('data', hold);

    /* `spawn' emits `error' on ENOENT, and an emitter with no listener for
       it throws -- a missing binary would surface as an exception from
       somewhere unrelated instead of as this program not starting. */
    child.on('error', (e) => { state.error = e; state.done = true; });
    child.on('exit', (code, signal) =>
    {
        Object.assign(state, { done: true, code, signal });
    });

    return {
        child,
        get done () { return state.done; },
        get output () { return state.output; },

        /* The group, then the pipes: a handle node still holds keeps the
           event loop alive whether or not anything writes to it. */
        kill ()
        {
            try { process.kill(-child.pid, 'SIGKILL'); } catch { /* gone */ }
            child.kill('SIGKILL');
            child.stdout.destroy();
            child.stderr.destroy();
            child.unref();
        },

        why (waited)
        {
            const secs = (waited / 1000).toFixed(1);
            const how = state.error ? `could not be started: ${state.error.message}`
                : state.done ? `exited after ${secs}s (code ${state.code}, signal ${state.signal})`
                : `was still running after ${secs}s`;
            const tail = state.output.trim();

            return `\`${command} ${args.join(' ')}\` ${how}.` +
                   (tail ? `\nIts output was:\n${tail}` : '\nIt printed nothing.');
        },
    };
}

/* Poll `test' until it's true or `ms' pass; whether it came true. For
   things with no event to wait on: a file appearing, a port opening. */
export async function until (test, ms = 8000, every = 100)
{
    const end = Date.now() + ms;

    for (;;)
    {
        if (await test())
            return true;
        if (Date.now() > end)
            return false;
        await new Promise((ok) => setTimeout(ok, every));
    }
}
