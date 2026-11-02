# Receipt format, v1

Status: draft. Becomes stable at the `v0.1.0` tag. After that, changes bump `v`.

A receipt records one review run that called the model. It lets anyone check, without the
code, that the findings were produced by an attested NEAR AI Cloud TEE for one exact input.
Runs with no hidden regions make no model call and have no receipt.

## Encoding

- JSON, canonicalized with RFC 8785 (JCS).
- `receipt_id` = lowercase hex SHA-256 of the canonical bytes. It is not a field inside
  the receipt.
- All hashes are lowercase hex SHA-256. All byte strings are lowercase hex.

## Fields

```json
{
  "v": 1,
  "key": {
    "repo_id": 123456789,
    "pr": 7,
    "base_sha": "<40 hex>",
    "head_sha": "<40 hex>",
    "input_sha256": "<hash of diff bytes || 0x00 || title || 0x00 || body>",
    "model": "<canonical model id>",
    "prompt_hash": "<sha256 of prompts/vN.txt>"
  },
  "nonce_salt": "<16 bytes hex>",
  "nonce": "<32 bytes hex>",
  "request_sha256": "<hash of exact request body bytes>",
  "response_sha256": "<hash of exact response body bytes>",
  "signature": {
    "text": "<model>:<request_sha256>:<response_sha256>",
    "sig": "<hex>",
    "signing_address": "0x<20 bytes hex>",
    "algo": "ecdsa",
    "kind": "provider_tee"
  },
  "attestation_sha256": "<hash of the stored attestation report bytes>",
  "verification": {
    "tcb_status": "<as reported by the quote verifier>",
    "checks": ["a", "b", "c", "d", "e", "f", "g"],
    "verified_at": "<RFC 3339 UTC>"
  },
  "scan": {"detectors_version": "1", "candidates": 3},
  "findings_sha256": "<hash of canonical findings array>",
  "findings_count": 1,
  "rejected_ungrounded": 0,
  "created_at": "<RFC 3339 UTC>"
}
```

## Findings digest

`findings_sha256` = SHA-256 of `JCS([{candidate_id, severity, rationale_sha256}, ...])`, sorted
by `candidate_id`. The rationale is hashed, never stored, so a published finding can be matched
to its receipt without the receipt holding its text.

## Derived values

```
key_canonical = JCS(key)
nonce         = SHA-256(key_canonical || nonce_salt)
key_hash      = SHA-256(key_canonical)          # what goes on chain
```

## Never in a receipt

The diff, excerpts, file contents, PR title or body, finding text, rationale, repository
name, or any username.

## Verifying a receipt

1. Recompute `nonce` from `key` and `nonce_salt`.
2. Load the attestation report by `attestation_sha256`. Check the quote, then check that
   `report_data` = `signing_address` padded to 32 bytes ‖ `nonce`.
3. Check `signature.text` has the stated form and recover the EIP-191 signer. It must equal
   `signing_address`.
4. Optional: look up `key_hash` on the NEAR contract and compare its `receipt_hash` with
   `receipt_id`.
