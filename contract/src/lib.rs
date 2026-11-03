//! Hushmark receipt anchor (ADR-0004).
//!
//! One receipt hash per review key, written once and never overwritten. Only the contract's own
//! account may write, and the Hushmark service holds just a function-call access key on that
//! account limited to `anchor`: NEAR does not let such a key attach deposits, so a stolen key
//! can add anchors but can never move funds. Only hashes are stored: no repository names,
//! usernames or content.

use near_sdk::store::LookupMap;
use near_sdk::{env, near, require, AccountId, BorshStorageKey, PanicOnDefault};

#[near(serializers = [borsh])]
#[derive(BorshStorageKey)]
enum StorageKey {
    Anchors,
}

/// What is stored for one review key.
#[near(serializers = [borsh, json])]
#[derive(Clone, Debug, PartialEq)]
pub struct Anchor {
    pub receipt_hash: String,
    pub block_height: u64,
    pub timestamp_ns: u64,
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct Contract {
    anchors: LookupMap<String, Anchor>,
    count: u64,
}

fn require_sha256_hex(name: &str, value: &str) {
    require!(
        value.len() == 64 && value.bytes().all(|b| b.is_ascii_digit() || (b'a'..=b'f').contains(&b)),
        format!("{name} must be 64 lowercase hex characters (a SHA-256)")
    );
}

#[near]
impl Contract {
    #[init]
    pub fn new() -> Self {
        Self { anchors: LookupMap::new(StorageKey::Anchors), count: 0 }
    }

    /// Record `receipt_hash` for `key_hash`. Panics if this key was already anchored, so one
    /// review input has exactly one receipt on chain.
    pub fn anchor(&mut self, key_hash: String, receipt_hash: String) -> Anchor {
        require!(
            env::predecessor_account_id() == env::current_account_id(),
            "only the Hushmark anchor account may write"
        );
        require_sha256_hex("key_hash", &key_hash);
        require_sha256_hex("receipt_hash", &receipt_hash);
        require!(!self.anchors.contains_key(&key_hash), "this review key is already anchored");

        let anchor = Anchor {
            receipt_hash,
            block_height: env::block_height(),
            timestamp_ns: env::block_timestamp(),
        };
        self.anchors.insert(key_hash.clone(), anchor.clone());
        self.count += 1;
        env::log_str(&format!(
            "EVENT_JSON:{{\"standard\":\"hushmark\",\"version\":\"1.0.0\",\"event\":\"anchor\",\"data\":{{\"key_hash\":\"{key_hash}\",\"receipt_hash\":\"{}\"}}}}",
            anchor.receipt_hash
        ));
        anchor
    }

    /// Anyone can look up the receipt anchored for a review key.
    pub fn get(&self, key_hash: String) -> Option<Anchor> {
        self.anchors.get(&key_hash).cloned()
    }

    pub fn count(&self) -> u64 {
        self.count
    }

    pub fn owner(&self) -> AccountId {
        env::current_account_id()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::test_utils::{accounts, VMContextBuilder};
    use near_sdk::testing_env;

    const KEY: &str = "1111111111111111111111111111111111111111111111111111111111111111";
    const RECEIPT: &str = "2222222222222222222222222222222222222222222222222222222222222222";

    fn as_self() -> Contract {
        let mut ctx = VMContextBuilder::new();
        ctx.current_account_id(accounts(0)).predecessor_account_id(accounts(0)).block_height(7);
        testing_env!(ctx.build());
        Contract::new()
    }

    #[test]
    fn anchors_once_and_reads_back() {
        let mut c = as_self();
        let a = c.anchor(KEY.into(), RECEIPT.into());
        assert_eq!(a.receipt_hash, RECEIPT);
        assert_eq!(a.block_height, 7);
        assert_eq!(c.get(KEY.into()), Some(a));
        assert_eq!(c.count(), 1);
        assert_eq!(c.get(RECEIPT.into()), None);
    }

    #[test]
    #[should_panic(expected = "already anchored")]
    fn second_anchor_for_the_same_key_panics() {
        let mut c = as_self();
        c.anchor(KEY.into(), RECEIPT.into());
        c.anchor(KEY.into(), KEY.into());
    }

    #[test]
    #[should_panic(expected = "only the Hushmark anchor account may write")]
    fn other_accounts_cannot_write() {
        let mut c = as_self();
        let mut ctx = VMContextBuilder::new();
        ctx.current_account_id(accounts(0)).predecessor_account_id(accounts(1));
        testing_env!(ctx.build());
        c.anchor(KEY.into(), RECEIPT.into());
    }

    #[test]
    #[should_panic(expected = "64 lowercase hex")]
    fn rejects_anything_but_a_sha256() {
        as_self().anchor("Hushmark/acme-widgets#1".into(), RECEIPT.into());
    }

    #[test]
    #[should_panic(expected = "64 lowercase hex")]
    fn rejects_uppercase_hex() {
        as_self().anchor(KEY.into(), RECEIPT.to_uppercase().replace('2', "A"));
    }
}
