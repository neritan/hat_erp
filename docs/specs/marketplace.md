# Marketplace — Distributor Listings, Hotel Ordering

Status: **built** (2026-10-09) — awaiting HAT review. All open questions answered by HAT on 2026-10-09.
Builds on [connect-mvp.md](connect-mvp.md).

## Goal
Turn the HAT platform into a B2B marketplace: distributors publish the products and services they
have available, hotels browse them, order them, and HAT tracks every order and its commission. The
marketplace is a new front door to the existing *HAT Order Request* flow — orders, partnerships,
commission and ratings work as today.

## Decisions (HAT, 2026-10-09)
| Topic | Decision |
|---|---|
| Interface | ERPNext **desk** for all actors (no portal in this version) |
| Price | Listing has a **public price**; a hotel with an *Active* partnership sees its **partner price** |
| Moderation | **No approval** — listings go live immediately; only distributors *Verified by HAT* can publish |
| Availability | Simple status **Available / Out of Stock** (no stock quantities) |
| Products | The marketplace shows **products**; one product can be sold by **several distributors**, each with its own offer (price, minimum, lead time, stock) |
| New products | **Distributors add missing products** themselves (Create Product); HAT staff merge duplicates |
| Currency | **ALL** only for now |
| Delivery region | All listings shown to every hotel; hotel and distributor agree delivery between them. Coverage is an **optional filter**, never a block |
| Commission | Every registered party is a HAT partner, so every marketplace order carries commission. The rate is **not decided yet** → configurable in *HAT Settings*, default 0 |

## Actors & permissions
| Actor | Can see | Can do |
|---|---|---|
| HAT staff | all listings (published or not) | everything; unpublish any listing; verify distributors |
| Distributor | own listings | create, edit, publish/unpublish, mark Available / Out of Stock |
| Hotel | published listings of all distributors (read-only) | filter/search, *Add to Order*, send orders (existing workflow) |

"Own" listings are enforced by the existing User Permission on `Supplier`.

## User stories
- As a **distributor**, I want to list my products with price, unit and minimum order, so that hotels can order from me without calling.
- As a **distributor**, I want to mark an item *Out of Stock* in one click, so that I don't receive orders I can't fulfil.
- As a **distributor** offering services (category 5), I want to list a service as *Price on Request*, so that hotels ask me for a quote.
- As a **hotel**, I want to browse listings by category, distributor, delivery region and rating, so that I find the right supplier fast.
- As a **hotel**, I want to see my partner price when I have a partnership, so that I know what I will actually pay.
- As a **hotel**, I want to add listings to an order and send it when ready, so that ordering from several distributors is easy.
- As **HAT staff**, I want to unpublish a listing that breaks the rules, so that the marketplace stays trustworthy.

## Product vs listing
- **Product** = ERPNext `Item` (code `HAT-<FB|KT|RM|TC|SV>-0001`, numbered per top-level category,
  non-stock, purchase + sales item). Shared catalogue: one product, many distributors.
- **Listing** = one distributor's **offer** of one product. A distributor can have only one listing
  per product.
- Distributors pick a product, or use **Create Product** (name incl. brand and pack size,
  category, unit). If a product with the same name exists it is reused, not duplicated. The
  distributor is added to the Item's Supplier table. Distributors cannot edit Items directly.
- The Item form shows its listings under *Connections → HAT Marketplace*.

## Data model
**Reused**
- `Supplier` (Distributor) — publishing allowed only when *Verified by HAT* is ticked.
- `Item Group` — listing category (HAT product tree, leaf groups only).
- `UOM`, `Currency` — unit and currency of the price.
- `HAT Partnership` — `discount_percentage` and `categories` give the partner price.
- `HAT Order Request` (+ Item) — the order; the hotel's *Draft* requests act as the cart.

**New DocType: `HAT Listing`** (module *Hospitality and Tourism Academy*, autoname `LST-.#####`)
| Field | Type | Notes |
|---|---|---|
| item | Link Item, required | **Product** from the catalogue |
| item_name | Data, fetched | product name, used for grouping and search |
| title | Data, required | defaults to the product name; the distributor may add offer details |
| distributor | Link Supplier, required | defaults to the user's Supplier |
| distributor_name | Data, fetched | |
| distributor_rating | Rating, fetched | kept in sync when hotels rate the distributor; sortable in the list |
| item_group | Link Item Group, fetched from product | leaf groups only |
| image | Attach Image | defaults to the product image |
| description | Text Editor | |
| price_type | Select: Fixed Price / Price on Request | default Fixed Price |
| price | Currency | required when Fixed Price |
| currency | Link Currency | fixed to ALL, read-only (kept as a field so EUR can be enabled later) |
| uom | Link UOM, fetched from product | the product's unit, e.g. Crate, Kg, Hour |
| minimum_qty | Float | default 1 |
| lead_time_days | Int | days from order to delivery |
| availability | Select: Available / Out of Stock | default Available |
| published | Check | default 1 |

**Changes to `HAT Order Request Item`**
- add `listing` (Link HAT Listing). When set, `item_group`, `item`, `description`, `uom`, `qty` (at least the minimum) and `rate` (price for this hotel) are filled from the listing.

## Hotel ordering flow (desk)
1. Hotel opens **Marketplace** (sidebar / workspace; desk page `/desk/hat-marketplace`): a grid
   of **product cards**. Each card lists every distributor selling the product, cheapest available
   first, with: distributor (link to the offer) and rating, price for this hotel (partner price
   with the public price struck through), minimum order and unit, lead time, availability, and a
   **Best price** badge when several distributors offer it. Filters: search (product, offer or
   distributor name), category (incl. sub-groups), *Available only*, optional *Delivers to my
   region*. 24 products per page, *Load more*. HAT staff pick a hotel to see its prices.
2. On a distributor's row the hotel clicks **Add to Order** (or **Request Quote** when priced on
   request) and enters a quantity. The **Listings** list (`HAT Listing`) keeps the same button for
   distributors and HAT staff managing offers.
3. The system adds the line to the hotel's **Draft** `HAT Order Request` for that distributor, creating it if none exists. One draft per hotel–distributor = one "cart" per distributor.
4. Hotel reviews the draft and runs **Send to Distributor** — from here the existing workflow applies (Sent → Accepted/Quoted → Delivered → Completed → rating).

## Rules
- Only published listings of Verified distributors are visible to hotels; unverifying a distributor hides its listings.
- *Out of Stock* listings stay visible but **Add to Order** is blocked.
- Quantity must be ≥ `minimum_qty`, and a listing must belong to the request's distributor (checked while Draft).
- **Price shown / rate used** = listing `price`, or `price × (1 − discount_percentage)` when the hotel has an *Active* partnership with that distributor that covers the listing's category (or has no categories set).
- Rate is copied when the line is added; later price changes do not affect existing lines. The distributor can still adjust when quoting.
- Request type (while Draft, when every line comes from a listing): **Order** if every line has a fixed price; **Request for Quotation** if any line is *Price on Request*.
- On *Send to Distributor*, warn if any listing became Out of Stock or unpublished since it was added.
- Distributor coverage is optional and informational: listings are never hidden or blocked by region.
  The existing out-of-coverage warning on the order request stays a warning.
- Commission: if the request has an Active partnership, its commission terms apply (as in Connect
  MVP); otherwise **HAT Settings → Default Commission Rate** is applied to the total and the request's
  Commission Type shows *HAT Default*. Default 0 until HAT decides the coefficient.

**New single DocType: `HAT Settings`**
| Field | Type | Notes |
|---|---|---|
| default_commission_rate | Percent | default 0; HAT staff only |

## Acceptance criteria
Verified 2026-10-09 on test data as real Hotel / Distributor / HAT users (21 checks, rolled back).
- [x] Verified distributor creates a listing → hotel sees it immediately; unverified distributor cannot publish
- [x] Distributor sees only own listings; hotel cannot edit any listing
- [x] Out of Stock listing cannot be added to an order
- [x] Hotel with 10% partnership sees 900 for a 1,000 listing; hotel without partnership sees 1,000
- [x] Adding listings from two distributors creates two Draft requests; adding again to the same distributor appends to the existing draft
- [x] A Price on Request line makes the request an RFQ
- [x] Qty below minimum is blocked
- [x] A hotel outside a distributor's coverage still sees and can order that distributor's listings
- [x] With HAT Settings commission 3% and no partnership, a 10,000 order gives 300 commission; at 0% it gives 0
- [x] A product sold by 3 distributors shows 3 offers, cheapest flagged Best price; partner price applied per distributor
- [x] Distributor creates a product (HAT-FB-…); same name returns the existing product; second listing of the same product by the same distributor is blocked
- [x] Partnership commission still wins over the default (5% on 9,000 = 450); distributor can accept a marketplace order
- [ ] Checked in the browser as Hotel, Distributor and HAT staff

## Future notes (HAT, 2026-10-09)
1. **Commission coefficient** — every registered party is a partner; HAT will decide the rate
   (and whether it differs by category, distributor or order size). Set it in HAT Settings.
2. **Price per hotel** — distributors may later set individual prices per hotel, beyond the
   partnership discount.
3. **EUR** — add when needed; the listing already has a currency field.
4. **Web portal** — maybe later, if the desk proves hard for hotels/distributors.

## Out of scope (this version)
Web portal, stock quantities, price per hotel, promotions, email notifications, payments.
