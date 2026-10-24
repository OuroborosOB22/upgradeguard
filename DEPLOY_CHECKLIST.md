# Before any public deploy

Nothing is deployed publicly yet. This list is what to walk through, and write the outcome next to each line with the date, before the site is exposed. A line with no recorded outcome is not done.

## Settings that must be set

- [ ] `UPGRADEGUARD_ACCESS_TOKEN` is a long random value (the site refuses to listen beyond localhost without it).
- [ ] `UPGRADEGUARD_REQUIRE_TOKEN=1` so a deployment without a token cannot start.
- [ ] `UPGRADEGUARD_HTTPS=1` and the site sits behind HTTPS (cookies become secure).
- [ ] `UPGRADEGUARD_SECRET` is fixed so sessions survive a restart.
- [ ] `UPGRADEGUARD_REMOTE_PROFILES`, if used, points at a file only the site account can read.
- [ ] Any model key lives in an environment variable named in `UPGRADEGUARD_EXPLAIN_KEY_ENV`. It is not in a file in the project.

## Try to break it

- [ ] Log in with a wrong token, many times: rate limit answers 429.
- [ ] Post to every form without the CSRF token, and with a token from another session: 403.
- [ ] Post from another origin (`Origin` and `Sec-Fetch-Site: cross-site`): 403.
- [ ] Project folder `../..`, an absolute path, a symlink out of `examples/`: refused.
- [ ] Package and version fields with shell characters, a 20 KB value, a null byte: refused, nothing run.
- [ ] A requirements file of 250 KB, one with 500 lines, one with a binary body: refused.
- [ ] A requirements file that names `<script>` or a markdown link: shown as plain text.
- [ ] Open `/runs/../x`, `/runs/<id>/evidence.zip` for an id that does not exist: 404, no path in the message.
- [ ] Trigger an error on purpose: the page shows no stack trace and no file path.
- [ ] Start more checks than the limits allow: 429 and a plain message.
- [ ] Remote profile: try to pass a host or user from the form: ignored, only configured names are accepted.
- [ ] Look at the response headers of every page: CSP, nosniff, frame denial, no referrer.
- [ ] Look in `logs/audit.log` and in the evidence folders for tokens, keys and home paths. None.

## What is not covered

- A virtual environment is not a sandbox. Only check example projects on a public site. Use the container runner for anything else.
- Dependency scanning of this project's own requirements (`pip-audit -r requirements.txt`) should run in CI. Record the result here.
- This checklist does not replace a review by someone who did not write the code.
