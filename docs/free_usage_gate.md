# Board Sense free public sampling gate

## Current rule

One anonymous visitor may consume one **physical board analysis** per UTC day. A single-board scan, a two-sided pair, a Spike Glass context/close-up pair, or a validated 2-6 photo case each counts as one board.

## Privacy

The gate stores a salted SHA-256 visitor identifier derived from network/browser signals. Raw IP addresses and exact coordinates are not stored. Referral source and coarse region fields are reserved for aggregate launch analytics.

## Important deployment note

`data/free_usage.json` is a development/fallback store only. Before public launch, production should point usage accounting at persistent shared storage (for example PostgreSQL/Supabase or another durable database). A container-local JSON file can reset on redeploy/restart and is not safe for multiple app instances.

Set a strong private `BOARD_SENSE_VISITOR_SALT` environment variable in production. Do not commit that secret to GitHub.
