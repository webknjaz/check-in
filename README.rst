check-in
========

It's a CLI tool for sending external commit examination info to GitHub
using Checks API on behalf of a GitHub App (bot context).


Defaults
--------
You can specify some default CLI option values via env vars. The tool also
supports dotenv concept. See example in ``.env.example``.


Missing parts
-------------
``check-in`` does some inputs validation, but it's not perfect. For example,
datetime args are strings accepted as is. This is likely to change in future,
but don't rely on it now.
