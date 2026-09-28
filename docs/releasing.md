# Releasing

One version covers both packages: `shotbox` on PyPI (the command and
`import shotbox`) and `shotbox` on npm (the Node helpers). It's in
`shotbox/__init__.py`, `package.json` and `package-lock.json`, and it's the
changelog's newest heading; `test/run.sh` fails if they disagree.

## A release

1. Set the version: `__version__` in `shotbox/__init__.py`, and
   `npm version X.Y.Z --no-git-tag-version` for the two npm files.
2. Turn the changelog's `## Unreleased` into `## X.Y.Z — DATE`, with a
   line or two on what the release is.
3. Merge that to main, then tag it and push the tag:

   ```
   git tag vX.Y.Z && git push origin vX.Y.Z
   ```

`.github/workflows/release.yml` then runs the tests (`ci.yml`, including
its build of both packages from scratch), checks the tag is the version,
and publishes to PyPI and npm.

## Once, before the first release

- **GitHub:** in the repository's settings, create two environments,
  `pypi` and `npm`. A required reviewer on them makes each publish wait
  for a click.
- **PyPI:** add a pending trusted publisher for the project `shotbox`
  (Account settings, Publishing): owner `mishan`, repository `shotbox`,
  workflow `release.yml`, environment `pypi`. The first release creates the
  project; no token.
- **npm:** trusted publishing is set up from a package's own settings, so
  it can't be for the first release. Make a granular access token that can
  publish, add it to the repository's secrets as `NPM_TOKEN`, and release.
  Then, on npmjs.com, in the package's settings, add a trusted publisher:
  GitHub Actions, `mishan/shotbox`, workflow `release.yml`, environment
  `npm`. Delete the secret and the token once a release has gone out
  without them.
