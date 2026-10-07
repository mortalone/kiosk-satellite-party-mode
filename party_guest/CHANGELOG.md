## 0.1.0

- Standalone guest portal independent of Kiosk and Party AI DJ; uses official MA's API.
- Direct `/guest/` browser URL with automatic queue-scoped session and ingress link.
- Own Kiosk connection and API token; optional remote AI search engine.
- Søg and Similar work with no AI service installed; hide AI when unavailable.
- HA controls for access/search permissions, resolved-result append only and expiring guest capabilities.
- Tests cover direct browsing, old session recovery, ingress link, disabled access, queue changes, host isolation and optional AI failures.
