/*
 * Copyright (C) 2026 Misha Nasledov <misha@nasledov.com>
 *
 * SPDX-License-Identifier: MIT
 */

/*
 * mutate.mjs -- a test's half of `shotbox mutate`.
 *
 *     const context = await browser.newContext();
 *     await mutated(context);
 *     const page = await context.newPage();
 *
 * In a run of `shotbox mutate`, it makes the run's change to every page
 * and frame of the context, and writes down whether the change was made
 * and proven; a clean run changes nothing and says which targets it saw.
 * Anywhere else it does nothing. Call it before the first page loads.
 *
 * The change is made by an init script, which runs before the page's own
 * scripts, CSP or not, in every frame. Its observer makes it as soon as
 * the target is there, in the callback, so no frame is drawn without it,
 * and again after a re-render. It finds the target as near as a page can
 * tell; whether it worked is Playwright's to say, by the locator the test
 * would use: once it's made, the test must find nothing by the target
 * showing.
 */

import fs from 'node:fs';

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

const BINDING = '__shotboxMutation';
const KINDS = new Set(['hide']);
/* More undos than this before a frame is drawn is a page fighting the
   change, and what the test does then says nothing of it. One a frame is
   a page drawing itself, as React does, which the change is made again
   before. */
const UNDOS = 10;
const FOUGHT = `the page undoes the change, over ${UNDOS} times before a frame is drawn`;
/* As long as a look at the pages may take, and closing waits for one:
   Playwright's first look by role, on a page of 50,000 elements, takes
   8 s. */
const LOOKING = 10000;
const SHOWN = 'the test could still find it, showing';
const WRAPPED = Symbol('shotbox.mutation');

/* What this process has found, for all its contexts, as a test runner
   makes one for each test: what one saw or proved stays so. The runner puts it together with its other processes'. */
let report = null, reporting = null;

export async function mutated (context)
{
    const { SHOTBOX_MUTATION: given, SHOTBOX_MUTATION_REPORT: out } = process.env;

    if (!given || !out || context[WRAPPED])
        return;
    const spec = JSON.parse(given);

    if (reporting !== out)
    {
        reporting = out;
        report = spec.kind ? { proven: false, why: 'the target was never seen, showing' }
                           : { seen: spec.targets.map(() => false) };
    }
    if (spec.kind && !KINDS.has(spec.kind))
    {
        report.why = `this shotbox can't make ${spec.kind} changes yet`;
        return write(out);
    }
    write(out);

    /* Why the target counts as still showing in `pages`, if it does: by
       Playwright's own locator, as the test would look for it, or because
       the look failed or took too long, which can't be taken for its
       being gone. */
    const look = async (pages) =>
    {
        try
        {
            const got = await Promise.race([showing(pages, spec.target),
                                            new Promise((ok) => setTimeout(ok, LOOKING).unref())]);

            return got === undefined ? 'it couldn\'t be looked for in time' : got ? SHOWN : '';
        }
        catch (e)
        {
            return pages.every((p) => p.isClosed()) ? 'the page closed before it could be looked for'
                : `it couldn't be looked for: ${e.message.split('\n')[0]}`;
        }
    };
    let proving = null;
    const done = () => proving;
    const opened = (page) => waits(page, done);

    waits(context, done);
    if (context.browser())
        waits(context.browser(), () => Promise.all(context.browser().contexts().map((c) => c[WRAPPED]?.())));
    context.pages().forEach(opened);
    context.on('page', opened);
    await context.exposeBinding(BINDING, async ({ page }, said) =>
    {
        if ('seen' in said)
            report.seen[said.seen] = true;
        else if (said.fought)
            Object.assign(report, { proven: false, fought: true, why: FOUGHT });
        else if (report.fought || report.proven || proving)
            return;
        else if (said.bad)
            report.why = `the page can't look for the target: ${said.bad}`;
        else
        {
            Object.assign(report, { made: true, why: 'the change was made, and not yet proven' });
            write(out);
            proving = look([page]).finally(() => proving = null);

            const why = await proving;

            if (report.fought)
                return;
            Object.assign(report, why ? { why } : { proven: true, why: '' });
        }
        write(out);
    });
    await context.addInitScript(inPage, { spec, binding: BINDING, undos: UNDOS });
    /* A page made before, as a test runner's own page is, until it next
       loads one. */
    for (const frame of context.pages().flatMap((p) => p.frames()))
        await frame.evaluate(inPage, { spec, binding: BINDING, undos: UNDOS }).catch(() => {});
}

/* Whether any frame of `pages` shows what the test could find by the
   target, by the locator it would use. */
async function showing (pages, t)
{
    const name = t.re === undefined ? t.name : new RegExp(`^(?:${t.re})$`);

    for (const frame of pages.flatMap((p) => p.frames()).filter((f) => !f.isDetached()))
    {
        const found = t.by === 'role' ? frame.getByRole(t.role, { name, exact: true })
            : t.by === 'text' ? frame.getByText(name, { exact: true }) : frame.locator(t.css);

        if (await found.filter({ visible: true }).count())
            return true;
    }
    return false;
}

/* Make `closing.close()` wait for `first` before it closes. */
function waits (closing, first)
{
    if (closing[WRAPPED])
        return;
    const close = closing.close;

    closing[WRAPPED] = first;
    closing.close = async function (...args)
    {
        await first();
        return close.apply(this, args);
    };
}

/* The report, as this process's own file in the run's report directory. */
function write (out)
{
    const to = `${out}/${process.pid}`;

    fs.writeFileSync(`${to}.part`, JSON.stringify(report));
    fs.renameSync(`${to}.part`, `${to}.json`);
}

/* The page's half, run in every frame from its source: it can use
   nothing outside itself. */
function inPage ({ spec, binding, undos })
{
    const key = Symbol.for('shotbox.mutation');

    if (globalThis[key])
        return;
    const send = globalThis[binding];
    const targets = spec.kind ? [spec.target] : spec.targets;
    const clean = (s) => s.replace(/\s+/g, ' ').trim();
    const said = (m) => Promise.resolve().then(() => send(m)).catch(() => {});
    let fought = false;

    globalThis[key] = true;

    /* The role, name and text the page gives it, as near as the page can
       tell: what Chromium gives it is only read through CDP. */
    const INPUTS = { button: 'button', submit: 'button', reset: 'button', image: 'button',
                     checkbox: 'checkbox', radio: 'radio', range: 'slider', number: 'spinbutton',
                     search: 'searchbox' };
    const DEFAULTS = { submit: 'Submit', reset: 'Reset' };
    const FIELDS = new Set(['input', 'select', 'textarea']);
    const TAGS = { button: 'button', textarea: 'textbox', nav: 'navigation', main: 'main',
                   dialog: 'dialog', ul: 'list', ol: 'list', li: 'listitem', option: 'option',
                   table: 'table', tr: 'row', td: 'cell', summary: 'button', section: 'region',
                   form: 'form', article: 'article', aside: 'complementary',
                   progress: 'progressbar', h1: 'heading', h2: 'heading', h3: 'heading',
                   h4: 'heading', h5: 'heading', h6: 'heading' };
    const CONTENT = new Set(['button', 'link', 'heading', 'cell', 'columnheader', 'rowheader',
                             'checkbox', 'radio', 'switch', 'option', 'tab', 'menuitem',
                             'treeitem', 'tooltip']);
    const UNSAID = new Set(['script', 'style', 'template', 'noscript']);
    const role = (el) =>
    {
        const given = el.getAttribute('role')?.trim().split(/\s+/)[0];

        if (given)
            return given;
        switch (el.localName)
        {
        case 'input': return INPUTS[el.type] ?? 'textbox';
        case 'a': case 'area': return el.hasAttribute('href') ? 'link' : null;
        case 'select': return el.multiple || el.size > 1 ? 'listbox' : 'combobox';
        case 'img': return el.getAttribute('alt') === '' ? 'presentation' : 'img';
        case 'th': return el.scope === 'row' ? 'rowheader' : 'columnheader';
        default: return TAGS[el.localName] ?? null;
        }
    };
    /* Hidden by its own style, not by what it's in, which may be shown
       later with nothing it holds changing. */
    const unshown = (c) =>
    {
        const style = getComputedStyle(c);

        return style.display === 'none' || style.visibility === 'hidden';
    };
    /* Its text, less what is hidden; for a name, with what its images
       and labeled parts are called. */
    const words = (n, named) => [...n.childNodes].map((c) =>
    {
        if (c.nodeType === Node.TEXT_NODE)
            return c.data;
        if (c.nodeType !== Node.ELEMENT_NODE || UNSAID.has(c.localName) || c.hidden
            || c.getAttribute('aria-hidden') === 'true' || unshown(c))
            return '';
        if (named && c.hasAttribute('aria-label'))
            return ` ${c.getAttribute('aria-label')} `;
        if (named && c.localName === 'img')
            return ` ${c.getAttribute('alt') ?? ''} `;
        return words(c, named);
    }).join('');
    /* Each source in turn, as finding a label can take a while. */
    const name = (el, as) =>
    {
        const ids = el.getAttribute('aria-labelledby');
        const root = el.getRootNode();
        const sources = [
            () => ids && ids.split(/\s+/).map((id) => root.getElementById?.(id)?.textContent ?? '').join(' '),
            () => el.getAttribute('aria-label'),
            () => FIELDS.has(el.localName) && el.labels && [...el.labels].map((l) => l.textContent).join(' '),
            () => (el.localName === 'img' || el.type === 'image') && el.getAttribute('alt'),
            () => el.localName === 'input' && ['button', 'submit', 'reset'].includes(el.type)
                  && (el.value || DEFAULTS[el.type]),
            () => CONTENT.has(as) && words(el, true),
            () => el.getAttribute('title'),
            () => el.getAttribute('placeholder'),
        ];

        for (const source of sources)
        {
            const s = clean(source() || '');

            if (s)
                return s;
        }
        return '';
    };
    const named = (t) =>
    {
        if (t.re === undefined)
            return (s) => s === clean(t.name);
        const re = new RegExp(`^(?:${t.re})$`);

        return (s) => re.test(s);
    };
    const nothing = () => false;
    const matches = targets.map((t) =>
    {
        try
        {
            if (t.by === 'css')
            {
                document.createDocumentFragment().querySelector(t.css);
                return (el) => el.matches(t.css);
            }
            const test = named(t);

            if (t.by === 'text')
                return (el) => test(clean(words(el)))
                               && ![...el.children].some((c) => test(clean(words(c))));
            return (el) =>
            {
                const as = role(el);

                return as === t.role && test(name(el, as));
            };
        }
        catch (e)
        {
            if (spec.kind)
                said({ bad: e.message });
            return nothing;
        }
    });
    /* For a role, not one aria-hidden leaves out, which a test can't find
       by its role either. */
    const showing = (el, t) => el.checkVisibility({ visibilityProperty: true })
                               && !(t.by === 'role' && el.closest('[aria-hidden="true"]'));

    const changed = new WeakSet();
    /* Those changed that are still in the page: what holds one is no text
       target, being no nearest element, and needn't be read again. */
    const live = new Set();
    const holds = (el) => [...live].some((c) => c.isConnected ? c !== el && el.contains(c)
                                                              : !live.delete(c));
    const hidden = (el) => el.style.getPropertyValue('display') === 'none'
                           && el.style.getPropertyPriority('display') === 'important';
    /* Without a transition, which would keep it showing a while. */
    const hide = (el) =>
    {
        el.style.setProperty('transition', 'none', 'important');
        el.style.setProperty('display', 'none', 'important');
    };
    /* Counted until a frame is drawn, or for a second where none is, as
       in a frame out of sight. */
    let undone = new Map(), since = performance.now();
    const again = (el) =>
    {
        if (hidden(el))
            return;
        if (performance.now() - since > 1000)
            [undone, since] = [new Map(), performance.now()];
        undone.set(el, (undone.get(el) ?? 0) + 1);
        if (undone.get(el) > undos)
        {
            fought = true;
            said({ fought: true });
            return;
        }
        hide(el);
    };
    const change = (el) =>
    {
        hide(el);
        changed.add(el);
        live.add(el);

        said({ made: true });
    };

    const seen = targets.map(() => false);
    /* What matches but isn't showing, looked at again each frame before
       it's drawn: a popover, a menu shown on hover or a style sheet can
       show it with nothing in the page changing. */
    const waiting = new Set();
    /* What is named by others, to look at again when they change. */
    const labelled = new Set();
    let looked = new Set();
    const visit = (el) =>
    {
        if (looked.has(el))
            return;
        looked.add(el);
        waiting.delete(el);
        if (el.hasAttribute('aria-labelledby'))
            labelled.add(el);
        for (let i = 0; i < targets.length; i++)
        {
            if (spec.kind && changed.has(el))
                again(el);
            else if ((spec.kind ? !(targets[i].by === 'text' && holds(el)) : !seen[i]) && matches[i](el))
            {
                if (!showing(el, targets[i]))
                    waiting.add(el);
                else if (spec.kind)
                    change(el);
                else
                {
                    seen[i] = true;
                    said({ seen: i });
                }
            }
        }
    };
    const watch = (root) => observer.observe(root, { childList: true, subtree: true,
                                                     attributes: true, characterData: true });
    const watched = new WeakSet();
    const scan = (root) =>
    {
        for (const el of [root, ...root.querySelectorAll('*')])
        {
            if (el.shadowRoot && !watched.has(el.shadowRoot))
            {
                watched.add(el.shadowRoot);
                watch(el.shadowRoot);
            }
            if (el.shadowRoot)
                scan(el.shadowRoot);
            if (el.nodeType === Node.ELEMENT_NODE)
                visit(el);
        }
    };
    const up = (n) => n.parentElement ?? n.parentNode?.host ?? n.host ?? null;
    /* What a change to `n` can have changed: what is in it, if `inside`;
       it, and if `outside` what it is in, whose text and names it is
       part of; and what it names, as a label. */
    const around = (n, inside, outside) =>
    {
        const el = n.nodeType === Node.ELEMENT_NODE ? n : up(n);

        if (inside && n.querySelectorAll)
            scan(n);
        for (let a = el; a; a = outside ? up(a) : null)
        {
            visit(a);
            if (a.control)
                visit(a.control);
            for (const r of a.id ? labelled : [])
            {
                if (!r.isConnected)
                    labelled.delete(r);
                else if (r.getAttribute('aria-labelledby')?.split(/\s+/).includes(a.id))
                    visit(r);
            }
        }
    };
    /* The attributes that can change the text or names of what holds the
       element, of all a busy page changes many times a second. */
    const NAMING = new Set(['hidden', 'aria-hidden', 'aria-label', 'alt']);
    const selectors = targets.filter((t, i) => t.by === 'css' && matches[i] !== nothing)
                             .map((t) => t.css);
    const observer = new MutationObserver((records) =>
    {
        looked = new Set();
        for (const r of records)
        {
            if (fought)
                return;
            for (const n of r.addedNodes)
                around(n, true, false);
            if (r.type === 'attributes')
                around(r.target, false, NAMING.has(r.attributeName));
            else
                around(r.target, false, true);
        }
    });
    /* What matches and wasn't showing, and what a selector finds, which
       can come to show or match with nothing it holds changing: by what
       holds it, a popover, a state such as :hover or :checked, or a style
       sheet. After each event that may have shown it, before anything
       else can look, and each frame before it's drawn. */
    const recheck = () =>
    {
        looked = new Set();
        for (const css of selectors)
            document.querySelectorAll(css).forEach(visit);
        for (const el of waiting)
        {
            if (el.isConnected)
                visit(el);
            else
                waiting.delete(el);
        }
    };
    for (const type of ['beforetoggle', 'mouseover', 'mouseout', 'focusin', 'focusout', 'change',
                        'transitionend', 'animationend'])
        addEventListener(type, () => queueMicrotask(recheck), true);
    const frame = () =>
    {
        [undone, since] = [new Map(), performance.now()];
        recheck();
        if (!fought)
            requestAnimationFrame(frame);
    };
    const attach = Element.prototype.attachShadow;

    /* A shadow root filled after the page has loaded changes nothing an
       observer outside it hears of. */
    Element.prototype.attachShadow = function (init)
    {
        const root = attach.call(this, init);

        if (init?.mode === 'open')
        {
            watched.add(root);
            watch(root);
        }
        return root;
    };
    watch(document);
    /* What a page made before mutated() has already. */
    scan(document);
    requestAnimationFrame(frame);
}
