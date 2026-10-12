// The bridge's plumbing: who we are, how we reach the host, what we report.
//
// Three files, served in this order and sharing one namespace rather than one
// closure, so a stack trace names a real file:
//
//     bridge-runtime.js   this -- session, transport, logging, reporting
//     bridge-page.js      shims the editor's page needs from a desktop host
//     bridge-desktop.js   window.AscDesktopEditor itself
//
// Plain scripts, not modules: the editor must find AscDesktopEditor already
// there when its own code runs, and a module is deferred.

((w) => {
  if (w.__libera__) return;

  const TAG = w === w.top ? "top" : "frame";

  // Which window's document this frame belongs to. The editor loads itself in
  // an iframe and forwards only the parameters it knows about, so the session
  // never reaches the inner frame's URL -- but the frames are same-origin, so
  // the top window's search string is readable from either.
  //
  // No catch. The one thing that throws here is a top window of another
  // origin, and "" -- which the host reads as "the first session" -- sent a
  // frame's requests to whichever window happened to be first.
  const SESSION = (() => {
    const m = /[?&]session=([^&]*)/.exec(w.top.location.search);
    return m ? m[1] : "";
  })();

  // Every /__host__/ URL goes through here: a request about a document has to
  // reach the session that holds it.
  function hostUrl(path) {
    if (!SESSION) return path;
    return `${path + (path.indexOf("?") === -1 ? "?" : "&")}session=${SESSION}`;
  }

  // ...and every host call goes through one of these. The five-line
  // XMLHttpRequest dance was written out at a dozen call sites, which is a
  // dozen chances to get the session, the content type or the error handling
  // subtly different from the others.
  //
  // XMLHttpRequest throughout, and staying that way: four of these calls are
  // synchronous because the editor makes them expecting the work to be
  // finished when the call returns, and fetch cannot do that. One idiom that
  // covers every case beats two that each cover half.

  function getFromHost(path, done) {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", hostUrl(path), true);
    if (done) xhr.onloadend = () => done(xhr);
    xhr.send(null);
  }

  // A small body is JSON, and says so; the change log and the canvas shot are
  // text, and say that instead.
  function postToHost(path, body, done, contentType) {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", hostUrl(path), true);
    xhr.setRequestHeader("Content-Type", contentType || "application/json");
    // An XHR answers a 500 without throwing, so a caller with no `done` would
    // never hear of one: say it, for the host's log. Not as an "error", which
    // offers a reload: a caller whose failure is worth one checks for itself.
    xhr.onloadend = done
      ? () => done(xhr)
      : () => {
          if (xhr.status < 200 || xhr.status > 299) {
            report("host", `${path} answered HTTP ${xhr.status}`);
          }
        };
    xhr.send(body === undefined ? null : body);
  }

  function getFromHostSync(path) {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", hostUrl(path), false);
    xhr.send(null);
    return xhr.status === 200 ? xhr.responseText : null;
  }

  function postToHostSync(path, body, contentType) {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", hostUrl(path), false);
    xhr.setRequestHeader("Content-Type", contentType || "application/json");
    xhr.send(body === undefined ? null : body);
    return xhr;
  }

  // A reply the host could not give, or gave as something other than JSON, is
  // the same as no reply: every caller here has a sensible default for it.
  function answer(xhr) {
    try {
      return JSON.parse(xhr.responseText) || {};
    } catch (_e) {
      return {};
    }
  }

  // Did the host put the document in *this* window? Opening a document gets
  // it a window of its own, and reloading this one would then throw away
  // whatever is open here -- which is the bug that made windows necessary.
  // Only a host with nowhere else to put it answers "here", and only a
  // document that opened is worth a reload: a cancelled File > Open answers
  // "here" too, and the window reloaded for nothing.
  function openedHere(xhr) {
    const said = answer(xhr);
    return !!(said.opened && said.here);
  }
  // One log for the whole window, shared by every frame's bridge: the top
  // frame's, whose bridge runs before the editor's iframe exists.
  const shared = w === w.top ? null : w.top.__libera__;
  const calls = shared ? shared.calls : [];
  // Every name called, kept. `calls` is emptied into each report, and the
  // report goes at once when the document is ready, so a test reading `calls`
  // for onDocumentContentReady could find it gone: the PDF editor's always was.
  // A global of its own, by this name, because tests/c_e2e reads it.
  w.top.__libera_seen = w.top.__libera_seen || new Set();
  const seen = w.top.__libera_seen;

  function preview(args) {
    return Array.prototype.map
      .call(args, (a) => {
        const s = typeof a === "string" ? a : a === null ? "null" : typeof a;
        return s.length > 60 ? `${s.slice(0, 60)}\u2026` : s;
      })
      .join(", ");
  }

  function log(name, args, ret) {
    const p = preview(args);
    calls.push({ frame: TAG, name: name, args: p });
    seen.add(name);
    console.log(
      "[libera:" +
        TAG +
        "] " +
        name +
        "(" +
        p +
        ")" +
        (ret === undefined ? "" : ` -> ${ret}`),
    );
  }

  const out = [];
  function report(kind, text) {
    out.push({ frame: TAG, kind: kind, text: String(text) });
  }
  w.addEventListener("error", (e) => {
    report("error", `${e.message || e.type} @ ${e.filename || "?"}:${e.lineno || 0}`);
  });
  w.addEventListener("unhandledrejection", (e) => {
    report("reject", e.reason);
  });
  const _err = console.error;
  console.error = function () {
    report("console.error", Array.prototype.join.call(arguments, " "));
    _err.apply(console, arguments);
  };

  // Ship what we saw back to the host, so a run is checkable without a human
  // reading a console. Errors included -- those are the real signal.
  function sendReport() {
    if (!out.length && !calls.length) return;
    postToHost(
      "/__host__/page-log",
      JSON.stringify({ events: out.splice(0), calls: calls.splice(0) }),
      // Not reported when it fails: the report would go the same way, and
      // one more would queue every second the host is not there.
      () => {},
    );
  }
  setInterval(sendReport, 1000);

  // Everything the other two files need from this one. A namespace rather
  // than a closure, because they are separate scripts.
  w.__libera__ = {
    w,
    TAG,
    SESSION,
    hostUrl,
    getFromHost,
    postToHost,
    postToHostSync,
    getFromHostSync,
    answer,
    openedHere,
    log,
    report,
    sendReport,
    calls,
  };
})(window);
