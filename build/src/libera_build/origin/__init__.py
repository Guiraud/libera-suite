"""The payload origin: the CDN the installer downloads from.

    place     where the payload lives, asked of the application itself
    cdn       one PUT per object, and what the CDN's answer means
    check     reading the origin back as a stranger, against a manifest
    collect   every builder's core here, and the manifest stamped over them
    publish   push, extras, windows: what goes up, in what order
    status    where a release has got to, and the next command

Separate verbs, because they fail differently and cost differently: collecting
is a quarter of a gigabyte over ssh, pushing the same again upward, checking a
read. A failed upload is retried on its own, without pulling everything across
the network again first.

**check is the verb a release did not have until 0.1.0 needed it.** An upload
tool reports success for a truncated body, for a redirect to an HTML error
page, and for an object written into the wrong prefix. The manifest the wheel
ships is what decides: fetch each URL the way a stranger's machine will, with
no token and no configuration, and hash it against what the application is
going to demand.
"""
