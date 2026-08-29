# demo_repo

A very small project we wrote so we can test UpgradeGuard on something we fully
control. It renders notes with Jinja2 and fetches them with Requests, and it has a
real pytest suite.

It uses `jinja2.Markup`, which Jinja2 removed in version 3.1. That gives us an
honest upgrade that really breaks, instead of a failure we made up.
