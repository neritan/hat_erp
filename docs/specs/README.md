# HAT Specs

## Features
| Feature | Spec | Status |
|---|---|---|
| Connect MVP: directory, order requests, partnerships, ratings | [connect-mvp.md](connect-mvp.md) | built — awaiting HAT review |
| Marketplace: distributor listings, hotel ordering | [marketplace.md](marketplace.md) | built — awaiting HAT review |

## Decisions log
| Date | Decision |
|---|---|
| 2026-10-01 | Hotels = ERPNext Customer (group "Hotel"); Distributors = ERPNext Supplier (group "Distributor") |
| 2026-10-01 | HAT staff, distributors and hotels all use the system |
| 2026-10-01 | "Connect" = directory + ordering/RFQ + contracts/partnerships; more to define together |
| 2026-10-01 | HAT earns from connections; model to be decided |
| 2026-10-01 | Hotels: geolocation and stars matter; distributors: categories, delivery coverage, rating by hotels |
| 2026-10-01 | Product tree from "Pema e produkteve ERP.doc" → `docs/product_categories.md` |
| 2026-10-09 | Marketplace: distributors list available items, hotels order them; desk UI; public + partner price; no listing approval (verified distributors only); Available/Out of Stock |
| 2026-10-09 | Marketplace prices in ALL only; listings shown to all hotels regardless of coverage (coverage = optional filter) |
| 2026-10-09 | Every registered party is a HAT partner → commission on every order; coefficient TBD (HAT Settings, default 0) |
| 2026-10-09 | Future: price per hotel, EUR, maybe a web portal |
| 2026-10-09 | Marketplace shows products (ERPNext Item); one product can be offered by several distributors (HAT Listing = offer) |
| 2026-10-09 | Distributors can add missing products themselves; HAT staff merge duplicates |
