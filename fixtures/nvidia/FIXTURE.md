# NVIDIA NRAS public keys, pinned

`jwks.json` is NVIDIA's NRAS key set, downloaded unedited from
https://nras.attestation.nvidia.com/.well-known/jwks.json at unix time 1793621879
(2026-11-02). NVIDIA rotates these keys, so offline verification of the recorded NRAS tokens uses
this pinned copy. Every key that signed a token in `fixtures/recordings/*/nras.json` is in it.
