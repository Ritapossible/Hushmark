// Renders the evidence cards from evidence.js, which scripts/build_site_data.py generates
// from the real recordings. Text is inserted with textContent, never as HTML.
(function () {
  const list = document.getElementById("evidence-list");
  const data = window.HUSHMARK_EVIDENCE;
  if (!list) return;
  if (!Array.isArray(data)) {
    list.textContent = "Evidence could not be loaded.";
    return;
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function short(hex) {
    return hex.length > 18 ? hex.slice(0, 10) + "…" + hex.slice(-6) : hex;
  }

  list.replaceChildren();
  for (const item of data) {
    const card = el("article", "card");

    const head = el("div", "ev-head");
    head.append(el("span", "ev-id", "// " + item.id));
    const hits = item.findings.length;
    head.append(
      hits
        ? el("span", "badge badge-hit", hits + (hits === 1 ? " finding" : " findings"))
        : el("span", "badge badge-clear", "no findings")
    );
    card.append(head);

    card.append(el("h3", null, item.title + "."));
    card.append(el("p", "ev-desc", item.description));

    for (const f of item.findings) {
      const box = el("div", "ev-finding");
      box.append(el("span", "where", f.where + " · line " + f.line + " · " + f.severity));
      box.append(el("p", null, f.rationale));
      card.append(box);
    }

    const facts = el("dl", "ev-facts");
    const rows = [
      ["verified", item.verified ? "checks a–g passed" : "not verified", item.verified ? "ok" : ""],
      ["signature", item.signatureKind, ""],
      ["intel tdx", item.tcbStatus, ""],
      ["signer", short(item.signer), ""],
      ["receipt", short(item.receiptId), ""],
    ];
    for (const [k, v, cls] of rows) {
      facts.append(el("dt", null, k));
      facts.append(el("dd", cls, v));
    }
    card.append(facts);
    list.append(card);
  }
})();
