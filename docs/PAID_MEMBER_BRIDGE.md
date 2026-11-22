# Member Board Sense bridge contract (draft / not live)

**Status:** This repository branch defines a Board Sense outbound membership client only.
It does not import that client into `main.py`, change the one-free-board public
sampler, create user-visible paid routes, touch Railway, or enable real payments.

## Planned request path

1. The browser logs into the customer Auth service and obtains a session JWT.
   The client may submit that JWT to Board Sense in `Authorization: Bearer ...`
   only over HTTPS, **not** in a query parameter or image metadata.
2. Board Sense performs existing image/type/size validation first. For a
   separately selected, paid-member request, it creates one **server-side
   UUID** representing **one physical board**. Two to six photographs of that
   board share the same ID and count as a single case.
3. Board Sense asks the trusted Scrap Radar backend to reserve that case.
   `member_board_bridge.reserve_paid_case` sends a HTTPS request:
   `POST /api/internal/board/cases/reserve`
   with body `{"case_id":"<server UUID>"}`, forwarded customer JWT, and
   **server-only** `X-SRF-Board-Service-Key`.
   No posted customer ID, plan selection, price, or quota amount is trusted.
4. The Scrap Radar backend endpoint **does not exist yet**. Before it is
   implemented or enabled, it must independently verify the customer JWT
   against the managed Auth provider, independently authenticate Board Sense
   using the service credential, and require *production provider-reconciled*
   subscription evidence. The PayPal sandbox pilot must not unlock access.
   The endpoint then atomically reserves the case through the internal quota
   foundation proposed in Scrapradar-backend draft PR #3.
5. Proposed success contract:
   ```json
   {
     "allowed": true,
     "case_id": "<same server UUID>",
     "usage": {
       "used_today": 1,
       "remaining": 24,
       "limit": 25,
       "day_utc": "2026-11-22"
     }
   }
   ```
   Any non-success response, malformed answer, expired token, outage, or
   unconfigured key **must deny paid analysis**. A paid-member request must
   **never** silently fall back to one free public case or tester bypass.
6. Only once a reservation succeeds, proceed with board analysis.
   For duplicate `RESERVED` or `COMPLETE` case ID, fetch/poll the original
   case result rather than rerun the expensive analysis. A completed board
   always consumes one case. If the backend has incontrovertible evidence
   of a server-side failure before completion, it may release that reservation
   via a trusted, non-public operation. Do not expose a customer-controlled
   release method.

## Security boundaries

- The outbound client is **disabled by default** and does not call anything
  when `BOARD_SENSE_MEMBER_BRIDGE_ENABLED` is unset.
- `SCRAP_RADAR_BOARD_SERVICE_KEY` must be at least 32 non-whitespace
  characters, injected through private server environment configuration,
  never copied to GitHub Pages or a JavaScript bundle.
- `SCRAP_RADAR_MEMBERSHIP_ORIGIN` is restricted to the exact known HTTPS
  Railway hostname. No open redirect is followed, because OAuth bearer
  tokens/service keys must not leak to redirected destinations.
- Do not log the bearer token, service key, raw image, email, or payment data.
- The proposed production membership service must reject client requests
  without both the service credential **and** a verified current customer
  identity. Successful membership-provider authentication must not be
  inferred from a browser redirect, local JWT payload parsing, sandbox
  purchase, or customer-authored `plan` field.
- Review the Board Sense Cloudflare origin proxy middleware as a **separate**
  security boundary. A public proxy header is not a substitute for internal
  service authentication.
- Enabling this requires explicit staged end-to-end tests, including duplicate
  analysis submissions, simultaneous 25/26th cases, midnight reset, cancellation,
  failed payment, identity expiry, backend outage, and no accidental free
  allowance consumption. No paid gate should be merged live before that.

## Tests

`python -m unittest discover -v -s tests -p 'test_member_board_bridge.py'`

All calls are offline/mock-only and cannot contact production.
