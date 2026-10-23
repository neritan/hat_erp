# Quote Requests — Hotels Ask, Distributors Compete

Status: **built** (2026-10-09) — awaiting HAT review. Builds on [marketplace.md](marketplace.md)
and [connect-mvp.md](connect-mvp.md).

## Goal
The marketplace lets hotels buy what distributors offer. Quote Requests are the reverse: a hotel
publishes what it needs (one or more products and quantities) and every interested distributor
answers with a sealed quote. The hotel compares the quotes line by line and awards each product to
the distributor it prefers; HAT turns each award into an order and earns its commission as usual.

## Decisions (HAT, 2026-10-09)
| Topic | Decision |
|---|---|
| Who sees a request | **Verified distributors whose categories match** the requested products (their *Categories Supplied*, or a listing in that category) |
| Quotes | **Sealed** — a distributor sees only its own quote; the hotel and HAT see all |
| Award | **Per product line** — each line can go to a different distributor; one order per winner |
| Hotel identity | **Visible** to distributors: name, city, stars |

## Actors & permissions
| Actor | Can see | Can do |
|---|---|---|
| Hotel | own requests; submitted quotes on them | create, publish, close, cancel requests; compare and award quotes |
| Distributor | open/closed/awarded requests matching its categories, and any request it quoted | create one quote per request, submit, update until the deadline, withdraw |
| HAT staff | everything | everything; act for a hotel |

Award details on request lines (winning distributor and rate) are visible only to the hotel and HAT staff.

## User stories
- As a **hotel**, I want to ask for prices on several products at once, so that I don't call every distributor.
- As a **hotel**, I want to compare quotes side by side and pick the best per product, so that I pay less.
- As a **distributor**, I want to be told when a hotel needs what I sell, so that I can win new customers.
- As a **distributor**, I want my prices pre-filled from my marketplace listings, so that quoting is fast.
- As **HAT staff**, I want awards to become normal orders, so that delivery, commission and ratings work as today.

## Data model
**`HAT Quote Request`** (`QR-YYYY-#####`): hotel (+ name, city, stars, territory fetched), title,
status (Draft / Open / Closed / Awarded / Cancelled), quote deadline, required by, delivery
address, notes, number of quotes, items (`HAT Quote Request Item`: product (optional Item),
category (Item Group), description, qty, unit; award fields at permlevel 1: awarded quote,
awarded distributor, awarded rate).

**`HAT Quote`** (`QT-YYYY-#####`): quote request, hotel (fetched), distributor, status (Draft /
Submitted / Awarded / Not Awarded / Withdrawn), valid until, delivery days, notes, total,
items (`HAT Quote Item`: request line, product, category, description, qty, unit, can supply,
rate, amount, remarks). One quote per distributor per request.

**`HAT Order Request`**: new read-only links *Quote Request* and *Quote*.

## Workflow
| From | Action | To | Who |
|---|---|---|---|
| Request Draft | Publish | Open | Hotel, HAT staff — notifies matching distributors |
| Request Open | Close (or deadline passes, hourly job) | Closed | Hotel, HAT staff, system |
| Request Open / Closed | Award | Awarded | Hotel, HAT staff |
| Request Draft / Open / Closed | Cancel | Cancelled | Hotel, HAT staff |
| Quote Draft | Submit Quote | Submitted | Distributor, HAT staff — notifies the hotel |
| Quote Submitted | (edit and save) | Submitted | Distributor, until the deadline while the request is Open |
| Quote Draft / Submitted | Withdraw | Withdrawn | Distributor, HAT staff |

**Award**: the hotel chooses one submitted quote per line (default: cheapest), may leave lines
unawarded. For each winning distributor one `HAT Order Request` (type *Order*) is created with
the quoted rates and sent to the distributor (*Send to Distributor*); the distributor then runs
*Accept Order* as usual. Quotes become *Awarded* (won at least one line) or *Not Awarded*.

## Rules
- A request needs at least one line; categories must be product groups (leaf).
- Publishing needs a deadline in the future.
- Quotes only on Open requests, before the deadline; a submitted quote needs a rate on at least
  one line it can supply.
- Distributors must be verified and match at least one requested category.
- Marketplace product cards have **Request Quotes**: adds the product to the hotel's Draft quote request.
- Commission on resulting orders: unchanged (partnership terms or HAT default).

## Acceptance criteria
Verified 2026-10-09 on test data as real Hotel / Distributor users (32 checks, rolled back).
- [x] Hotel creates and publishes a request; matching distributors see it, non-matching and unverified do not
- [x] Matching distributors are notified on publish; hotel is notified on quote submission
- [x] Quote is pre-filled with the distributor's listing prices
- [x] A quote always prices exactly the request's lines, however it is created (Send Quote or + New); a quote cannot be submitted without at least one price
- [x] Distributor A cannot see distributor B's quote; hotel sees both submitted quotes, not drafts
- [x] Distributors cannot read award fields on request lines
- [x] Quote after the deadline is blocked; hourly job closes expired requests
- [x] Split award creates one order per winning distributor with the quoted rates, sent to the distributor; quotes marked Awarded / Not Awarded
- [x] "Request Quotes" from the marketplace adds lines to the hotel's draft request
- [ ] Checked in the browser as Hotel and Distributor

## Open questions
1. Should distributors see how many quotes a request already has? (Now: yes, the count only.)
2. Should the hotel see quotes only after the deadline (sealed until opening)? (Now: as soon as submitted.)
3. Email notifications in addition to in-app ones?

## Out of scope (this version)
Email notifications, counter-offers / negotiation rounds, partial quantities per line, attachments
on quotes, automatic award.
