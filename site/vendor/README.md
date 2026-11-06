# Vendored browser code

`hushmark-crypto.js` gives the receipt verifier page (`verify.html`) the one thing WebCrypto
lacks: recovering the Ethereum-style (EIP-191, secp256k1, Keccak-256) address that signed a
receipt inside the TEE. Everything else on the page uses WebCrypto's SHA-256.

It is a single ES module, bundled so the site's Content-Security-Policy can stay
`script-src 'self'` (no CDN):

| Package | Version | Licence |
|---|---|---|
| `@noble/curves` | 2.4.0 | MIT |
| `@noble/hashes` | 2.0.1 | MIT |

Rebuild (from an empty folder, outside the repository):

```sh
npm install @noble/curves@2.4.0 @noble/hashes@2.0.1 esbuild@0.28.2
cp /path/to/Hushmark/site/vendor/hushmark-crypto.entry.js entry.js
npx esbuild entry.js --bundle --format=esm --minify --legal-comments=inline --outfile=hushmark-crypto.js
```

Then add back the two header comment lines. It was checked against the real TEE signature
in `fixtures/recordings/r1/signature.json` (recovers `0x3b75…fa0c`).
