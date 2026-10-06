# Board Sense public usage store: release checklist

Board Sense calls `public.board_sense_public_daily_usage` for a read and
`public.claim_board_sense_free_use` for an atomic daily claim. Both objects
already exist in the Scrap Radar Family Supabase project. The table has RLS
enabled, no public policies, and no table or function access for `anon` or
`authenticated`. The project had no usage rows at the time of this review.

The Python change stops sending unverified referral and location headers to
the claim function. Its existing optional arguments remain available for
compatibility, and its existing table has nullable location columns. New
claims from Board Sense will store a salted, truncated visitor hash, a count,
and UTC timestamps; no location values will be sent.

## Order of operations

1. Confirm the intended Supabase project remains healthy and the usage
   table/function grants remain restricted to `service_role`.
2. In Railway's **Board Sense production service settings**, set
   `SUPABASE_URL` to the intended project's HTTPS API URL, and set either
   `SUPABASE_SECRET_KEY` to a server-only `sb_secret_...` key or
   `SUPABASE_SERVICE_ROLE_KEY` to a legacy service-role key. Set a strong
   `BOARD_SENSE_VISITOR_SALT` there as well. Never paste these secrets into
   GitHub, browser code, chat, or logs. Use a dedicated key if available.
3. Confirm the database and API are reachable from the service, then merge and
   deploy the production fail-closed gate. Without a working database or key,
   that gate returns HTTP 503 for public analyses.
4. Check one non-tester scan consumes one allowance and a second scan from the
   same browser/network is declined. Check an allowed tester still works.
   Verify that a failed database call returns HTTP 503, not a free local claim.
5. Establish a retention period and a protected cleanup process for historical
   usage rows before opening the service to public traffic.

The service-role/secret key bypasses RLS. Restrict it to Railway server
variables; the table's RLS and revoked public grants protect against
anonymous direct API access. The hash uses the canonical client IP and is a coarse anonymous network limit:
changing User-Agent does not create another allowance, but changing networks can.

On October 6, 2026, the paused project was restored and its existing claim
function was hardened through the committed migration. It retains the existing
table and optional arguments, uses a UTC date explicitly, validates claims, and
keeps execution restricted to `service_role`. A rolled-back test verified first
claim allowed, duplicate rejected, without retaining a test usage row.

The security advisor's informational [RLS enabled without policies](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy)
notice is intentional for this server-only table: `anon` and `authenticated`
have no grants or policies. Do not add a public policy to silence that notice.

The October release code reserves a claim before analysis and fails closed in
production without persistent accounting. Railway still needs to deploy that
release. Changing the hashing scheme resets anonymous buckets once on rollout;
do not rotate `BOARD_SENSE_VISITOR_SALT` during a usage day.
