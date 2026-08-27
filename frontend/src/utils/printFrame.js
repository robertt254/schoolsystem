// Print a single DOM element in complete isolation from the rest of the app.
//
// The old approach (`.print-area` + `visibility:hidden` on everything else,
// then `window.print()`) looks right but has a well-known failure mode: a
// `visibility:hidden` element still reserves its full layout box, and any
// `overflow-y-auto` container (the app's <main>, most page bodies) stops
// clipping its content once printing starts — so the *entire* underlying
// page (sidebar, long tables, whatever else is on screen) still contributes
// its full height to the document even though none of it is painted. Print
// pagination is driven by that height, so a receipt opened over a long page
// (a big payment log, a long roster) came out as several mostly-blank pages
// with the receipt only appearing on the first one.
//
// Printing the element inside a throwaway iframe with its own document sidesteps
// this entirely: that document contains nothing but the element itself, so it
// paginates to exactly the content's own size. The iframe clones every
// stylesheet from the main document (so Tailwind classes, brand colours and
// the `print:` variants still resolve identically) but nothing else.
export function printElement(element, title = 'Print') {
  if (!element) return;

  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
    .map((node) => node.outerHTML)
    .join('\n');

  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  iframe.setAttribute('aria-hidden', 'true');
  document.body.appendChild(iframe);

  let cleaned = false;
  const cleanup = () => {
    if (cleaned) return;
    cleaned = true;
    if (iframe.parentNode) iframe.parentNode.removeChild(iframe);
  };

  const doc = iframe.contentWindow.document;
  doc.open();
  doc.write(`<!doctype html><html><head><title>${title}</title>${styles}
    <style>
      @page { margin: 10mm; }
      html, body { margin: 0; background: #fff; }
      /* Tailwind's spacing/font-size utilities are rem-based, sized off the
         root font-size — shrinking it here scales every printed document
         (fonts, padding, gaps) down proportionally in one place, with zero
         effect on the live app's own (unrelated) root font-size. On-screen
         sizing was designed for a monitor, not a sheet of paper. */
      html { font-size: 13px; }
    </style>
  </head><body>${element.outerHTML}</body></html>`);
  doc.close();

  // Fires once the written document — including its linked stylesheets —
  // has finished loading. Setting this before write()/close() is safe: the
  // handler binds to the iframe element, and the synchronous write() call
  // below replaces the placeholder document before its own load event can
  // fire, so this only ever fires for the real content.
  iframe.onload = () => {
    try {
      iframe.contentWindow.focus();
      iframe.contentWindow.print();
    } catch (e) {
      console.error('Print failed', e);
    }
  };

  // Some browsers fire `afterprint` on the iframe's window once the print
  // dialog closes — clean up there when available. Always have a fallback
  // timer too, in case a browser never fires it.
  try {
    iframe.contentWindow.addEventListener('afterprint', cleanup);
  } catch (e) { /* ignore */ }
  setTimeout(cleanup, 60000);
}
