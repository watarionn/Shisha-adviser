# Public known-anchor evidence v3.0.1

## Free Cuba / STARLINE

Purpose: provide a useful fallback when a named reference flavor is known but is not yet present in the scored recommender dataset.

Observed profile from current public sources:
- cola-led flavor with lime/citrus notes
- refreshing/light direction
- mint or citrus is commonly suggested as an addition

Sources checked 2026-09-16:
- CLOUD SHOP, STARLINE Free Cuba product page: https://shop.cloud-jp.net/products/starline-free-buba-50g
- CLOUD, STARLINE / DARKSIDE overview: https://cloud-jp.net/starline-darkside/
- NEWEMO SHISHA, Free Cuba 50g: https://newemoshisha.com/products/starline-free-cuba-50g

Public UI behavior:
- Free Cuba is explicitly labeled as absent from the scored recommender dataset.
- Suggested items are shown as reference candidates, not computed compatibility scores.
- Candidate names are limited to flavors already present in the local audited recommender dataset.
- Current candidate direction: mint, lime, lemon-mint, citrus-mint.
