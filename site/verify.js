// Verify a Hushmark receipt in the browser, without trusting Hushmark (docs/UPGRADES.md #4).
// The same checks as hushmark/receipt_check.py, as far as a browser can go: receipt ID, nonce,
// the TEE's signature and the NEAR testnet anchor. Intel's quote and NVIDIA's GPU verdict need
// the attestation report and `hushmark-verify`; the page says so instead of pretending.
// Nothing leaves the page except one read-only call to the public NEAR testnet RPC.
import { recoverAddress } from "./vendor/hushmark-crypto.js";

const RPC = "https://rpc.testnet.near.org";
const ANCHOR = "anchor.hushmark.testnet";
const enc = new TextEncoder();

const hex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
const fromHex = (h) => {
  if (!/^([0-9a-f]{2})*$/i.test(h)) throw new Error("not hex");
  return Uint8Array.from(h.match(/../g) || [], (x) => parseInt(x, 16));
};
const sha256 = async (bytes) => hex(await crypto.subtle.digest("SHA-256", bytes));

// RFC 8785 for what receipts hold: objects, arrays, strings and integers.
function canonical(value) {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value && typeof value === "object") {
    return "{" + Object.keys(value).sort().map((k) => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
  }
  if (typeof value === "number" && !Number.isInteger(value)) throw new Error("receipts hold no floats");
  return JSON.stringify(value);
}

// Accept the bare receipt, or the check's whole details text with its ```json block.
export function extract(text) {
  const m = text.match(/```json\s*([\s\S]*?)```/);
  return (m ? m[1] : text).trim();
}

export async function verify(text, { online = true } = {}) {
  const raw = extract(text);
  const bytes = enc.encode(raw);
  const receiptId = await sha256(bytes);
  const checks = [];
  const add = (name, status, detail) => checks.push({ name, status, detail });

  let receipt;
  try {
    receipt = JSON.parse(raw);
    if (!receipt || typeof receipt !== "object" || !receipt.key) throw new Error("no key");
  } catch {
    add("Receipt ID", "fail", "This is not a Hushmark receipt (it is not the expected JSON).");
    return { receiptId, checks, ok: false, verdict: "Not verified" };
  }

  if (canonical(receipt) === raw) {
    add("Receipt ID", "pass", `The receipt's ID is the SHA-256 of its exact bytes: ${receiptId}`);
  } else {
    add("Receipt ID", "fail", "The bytes are not in canonical form, so they were edited or reformatted.");
  }

  const keyBytes = enc.encode(canonical(receipt.key));
  try {
    const salt = fromHex(String(receipt.nonce_salt));
    const nonce = await sha256(new Uint8Array([...keyBytes, ...salt]));
    if (nonce === receipt.nonce) {
      add("Nonce", "pass", "nonce = SHA-256(key ‖ salt): this review's own, so old evidence cannot be replayed.");
    } else {
      add("Nonce", "fail", "The nonce does not match the key and salt.");
    }
  } catch {
    add("Nonce", "fail", "The salt is not valid hex.");
  }

  try {
    const sig = receipt.signature || {};
    const text = `${receipt.key.model}:${receipt.request_sha256}:${receipt.response_sha256}`;
    if (sig.kind !== "provider_tee" || sig.algo !== "ecdsa") throw new Error("kind");
    if (sig.text !== text) throw new Error("text");
    const signer = recoverAddress(text, String(sig.sig));
    if (signer.toLowerCase() !== String(sig.signing_address).toLowerCase()) throw new Error("signer");
    add(
      "Signature",
      "pass",
      `The signature over the model's request and answer hashes matches the address named in this receipt (${sig.signing_address}). Any key can sign; whether this one is inside a TEE needs the check below.`,
    );
  } catch {
    add("Signature", "fail", "The signature does not cover these hashes, or does not match the address in this receipt.");
  }

  add(
    "Intel and NVIDIA evidence",
    "skipped",
    "Needs the attestation report (in the Action's receipt artifact) and the command: hushmark-verify receipt.json attestation.json",
  );

  if (!online) {
    add("NEAR anchor", "skipped", "Not looked up (offline).");
  } else {
    try {
      const keyHash = await sha256(keyBytes);
      const args = btoa(JSON.stringify({ key_hash: keyHash }));
      const r = await fetch(RPC, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: "hushmark",
          method: "query",
          params: { request_type: "call_function", finality: "final", account_id: ANCHOR, method_name: "get", args_base64: args },
        }),
      });
      const body = await r.json();
      const found = JSON.parse(new TextDecoder().decode(new Uint8Array(body.result.result)) || "null");
      if (!found) {
        add("NEAR anchor", "skipped", "No anchor for this review key (anchoring is optional).");
      } else if (found.receipt_hash === receiptId) {
        add("NEAR anchor", "pass", `Anchored on ${ANCHOR} at block ${found.block_height}; it can never be replaced.`);
      } else {
        add(
          "NEAR anchor",
          "fail",
          "A different receipt is the anchored one for this review key. A re-run makes a new receipt and only the first is anchored.",
        );
      }
    } catch {
      add("NEAR anchor", "skipped", "The NEAR testnet RPC could not be reached.");
    }
  }

  // This page cannot check Intel's or NVIDIA's evidence, so it never says "verified": a
  // receipt's own signature only proves that the key named inside it signed it (audit
  // 2026-11-08). hushmark-verify with the attestation report gives the full verdict.
  const status = Object.fromEntries(checks.map((c) => [c.name, c.status]));
  let verdict = "Signature matches; TEE not checked";
  if (!["Receipt ID", "Nonce", "Signature"].every((n) => status[n] === "pass")) {
    verdict = "Not verified";
  } else if (status["NEAR anchor"] === "fail") {
    verdict = "Not the anchored receipt";
  }
  return { receiptId, checks, ok: false, verdict, receipt };
}

// --- page wiring (skipped when imported outside a browser page) ---------------------------
if (typeof document !== "undefined" && document.getElementById("verify-form")) {
  const form = document.getElementById("verify-form");
  const input = document.getElementById("receipt-input");
  const out = document.getElementById("verify-result");
  const example = document.getElementById("load-example");

  const label = { pass: "Pass", fail: "Fail", skipped: "Skipped" };
  function show(result) {
    out.replaceChildren();
    const head = document.createElement("p");
    head.className = "verify-verdict " + (result.verdict === "Not verified" ? "is-bad" : "is-partial");
    head.textContent = result.verdict;
    out.append(head);
    if (result.receipt) {
      const facts = document.createElement("p");
      facts.className = "verify-facts";
      const k = result.receipt.key;
      facts.textContent = `Pull request #${k.pr} · model ${k.model} · ${result.receipt.scan?.candidates ?? "?"} hidden region(s) reviewed · ${result.receipt.findings_count} finding(s) · reviewed ${result.receipt.created_at}`;
      out.append(facts);
    }
    const list = document.createElement("ul");
    list.className = "verify-checks";
    for (const c of result.checks) {
      const li = document.createElement("li");
      li.className = "verify-check is-" + c.status;
      const tag = document.createElement("span");
      tag.className = "verify-tag";
      tag.textContent = label[c.status];
      const name = document.createElement("strong");
      name.textContent = c.name;
      const detail = document.createElement("span");
      detail.className = "verify-detail";
      detail.textContent = c.detail;
      li.append(tag, name, detail);
      list.append(li);
    }
    out.append(list);
    out.hidden = false;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    out.hidden = false;
    out.textContent = "Checking…";
    show(await verify(input.value));
  });
  example.addEventListener("click", async () => {
    input.value = await (await fetch("examples/receipt-pr17.json")).text();
    form.requestSubmit();
  });
}
