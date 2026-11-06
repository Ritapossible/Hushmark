// Hushmark receipt verifier: the only crypto the browser needs that WebCrypto lacks.
// Built from @noble/curves 2.4.0 and @noble/hashes 2.0.1 (MIT) with esbuild 0.28.2.
import { secp256k1 } from "@noble/curves/secp256k1.js";
import { keccak_256 } from "@noble/hashes/sha3.js";

const enc = new TextEncoder();
const hex = (b) => Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
const fromHex = (h) => Uint8Array.from(h.replace(/^0x/, "").match(/../g).map((x) => parseInt(x, 16)));

// EIP-191 personal_sign recovery: returns the 0x address that signed `text`.
export function recoverAddress(text, signatureHex) {
  const msg = enc.encode(text);
  const digest = keccak_256(new Uint8Array([...enc.encode(`\x19Ethereum Signed Message:\n${msg.length}`), ...msg]));
  const sig = fromHex(signatureHex);
  if (sig.length !== 65) throw new Error("signature must be 65 bytes");
  const v = sig[64] >= 27 ? sig[64] - 27 : sig[64];
  const recovered = new Uint8Array([v, ...sig.slice(0, 64)]);
  const pub = secp256k1.recoverPublicKey(recovered, digest, { prehash: false });
  const full = secp256k1.Point.fromBytes(pub).toBytes(false);
  return "0x" + hex(keccak_256(full.slice(1)).slice(12));
}
