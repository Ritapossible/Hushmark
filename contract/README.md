# Hushmark anchor contract

Stores one receipt hash per review key on NEAR, and refuses a second (ADR-0004).

| Method | Who | What |
|---|---|---|
| `new()` | once, at deploy | empty map |
| `anchor(key_hash, receipt_hash)` | only the contract's own account | stores the receipt hash; panics if `key_hash` exists |
| `get(key_hash)` | anyone (view) | `{receipt_hash, block_height, timestamp_ns}` or `null` |
| `count()` | anyone (view) | number of anchors |

Both arguments must be 64 lowercase hex characters. Nothing else is stored: no repository
names, usernames or content.

## Build and test

```sh
cargo test                               # 5 unit tests
cargo install cargo-near --locked --no-default-features
cargo near build non-reproducible-wasm   # target/near/hushmark_anchor.wasm
```

## Deployed

- Contract: [`anchor.hushmark.testnet`](https://testnet.nearblocks.io/address/anchor.hushmark.testnet),
  deployed 2026-11-02. On-chain code hash `A1QKAEQSGgwYXQwUL4yWfh64czifnjTtejgu1eDFpPTZ` =
  SHA-256 of `target/near/hushmark_anchor.wasm` built from this source.
- Service key: function-call key `ed25519:Gxpb82w5XgStK1aznwB77F2EpLAQqfLPk3xa61LjvCFN`,
  limited to `anchor` on this contract, 0.5 NEAR gas allowance.
- First anchor: demo PR #6's receipt `f0a01b7c…f21d8aa`
  ([tx](https://testnet.nearblocks.io/txns/6UQaEH9gvmeaCLYs2rVomtWjWoekH6edzqtmSxs4EmB9)).
  The same anchor again was refused, "this review key is already anchored"
  ([tx](https://testnet.nearblocks.io/txns/EH33MVqn6PsFWrGWJ1ebYd2u8eWV2amcNyBnq81yEKoe)).

## Deploy (testnet)

Accounts: `hushmark.testnet` (parent, full access, kept offline) and
`anchor.hushmark.testnet` (the contract).

```sh
near account create-account sponsor-by-faucet-service hushmark.testnet autogenerate-new-keypair save-to-keychain network-config testnet create
near account create-account fund-myself anchor.hushmark.testnet '3 NEAR' autogenerate-new-keypair save-to-keychain sign-as hushmark.testnet network-config testnet sign-with-keychain send
near contract deploy anchor.hushmark.testnet use-file target/near/hushmark_anchor.wasm with-init-call new json-args '{}' prepaid-gas '30 Tgas' attached-deposit '0 NEAR' network-config testnet sign-with-keychain send
```

Then the service key: a function-call access key on `anchor.hushmark.testnet` that can call only
`anchor`, with no allowance for deposits:

```sh
near account add-key anchor.hushmark.testnet grant-function-call-access --allowance '0.5 NEAR' --contract-account-id anchor.hushmark.testnet --function-names anchor autogenerate-new-keypair print-to-terminal network-config testnet sign-with-keychain send
```

Store the printed private key as the repository secret `NEAR_ANCHOR_KEY`, and set the
repository variable `NEAR_ANCHOR_ACCOUNT=anchor.hushmark.testnet`. The allowance only pays gas;
function-call keys cannot attach deposits or transfer funds.
