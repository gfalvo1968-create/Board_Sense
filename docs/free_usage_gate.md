# Board Sense free public sampling gate

## Current rule

One anonymous network may start one **physical board analysis attempt** per UTC day. A single-board scan, a two-sided pair, a Spike Glass context/close-up pair, or a validated 2-6 photo case each counts as one attempt. All photos are validated before an atomic claim; analysis starts only after a successful claim. Invalid uploads do not consume an allowance. A started analysis, including an identity halt or an analysis error, does consume it.

## Privacy

The gate stores a salted SHA-256 identifier derived from a canonical network address. Changing User-Agent cannot reset it. Raw IP addresses and exact coordinates are not stored. People sharing a public network also share an allowance; changing networks can still evade this anonymous sampling limit. It is not account authentication. Supabase claims do not forward location/referral headers.

## Important deployment note

`data/free_usage.json` is for development only. Production requires the configured Supabase key, URL and visitor salt and returns 503 when persistent accounting is unavailable. There is no production fallback to a container-local file.

Set a strong private `BOARD_SENSE_VISITOR_SALT` environment variable in production. Do not commit that secret to GitHub.

Private original uploads are deleted after processing, rejection or failure. Generated blueprints remain in service storage and can be opened by anyone possessing their random URL; they are not a private archive. Establish blueprint and usage-history retention before public launch.
