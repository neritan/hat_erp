# Connect MVP — Directory, Ordering, Partnerships, Ratings

Status: **built** (2026-10-01), first version for HAT review. Defaults chosen without HAT
confirmation are marked ⚠ and listed under Open questions.

## Goal
Give HAT one place to connect Distributors with Hotels: find distributors by category and
delivery area, track requests and orders between them, record partnership terms including HAT's
commission, and let hotels rate distributors.

## Actors & permissions
| Actor | Role | Can see | Can do |
|---|---|---|---|
| HAT staff | `HAT Staff` | everything | create/edit hotels, distributors, partnerships, requests; run every workflow step; mark distributors *Verified* |
| Hotel | `Hotel` | all distributors, catalogue; own requests, partnerships, ratings ⚠ | create & send requests, accept/reject quotes, confirm receipt, rate distributors |
| Distributor | `Distributor` | hotels; own requests, partnerships, ratings ⚠ | quote, accept orders, decline, mark delivered |

"Own" is enforced by a **User Permission** linking the user to their Customer / Supplier record.

## Data model
**Reused from ERPNext**
- `Customer` (group **Hotel**) + custom fields: Stars, Property Type, Number of Rooms, City,
  Latitude, Longitude. Region = standard `territory` (Albania's 12 counties).
- `Supplier` (group **Distributor**) + custom fields: Categories Supplied, Delivery Coverage,
  Minimum Order, Verified by HAT (HAT staff only), Average Rating, Number of Ratings.
- `Item Group` — the product tree from `docs/product_categories.md` (5 categories → 24 subcategories → 59 groups).
- `Territory` — Albania → 12 counties ⚠.

**New DocTypes** (module *Hospitality and Tourism Academy*)
| DocType | Purpose |
|---|---|
| HAT Partnership | Terms between one distributor and one hotel: dates, categories, discount, payment terms, T&C, HAT commission (percentage / fixed per order / none) |
| HAT Order Request (+ Item) | Request for quotation or direct order from a hotel to a distributor; items by category, qty, rate; total and HAT commission |
| HAT Distributor Rating | Hotel's rating of a distributor: overall, quality, delivery, communication, comment |
| HAT Category / HAT Coverage Area | Child tables for multi-select categories and coverage |

## Workflows
**HAT Partnership** (HAT staff runs every step ⚠)
Draft → *Propose* → Proposed → *Approve* → Active / *Reject* → Rejected;
Active ⇄ Suspended (*Suspend* / *Reactivate*); Active or Suspended → *Terminate* → Terminated.

**HAT Order Request**
| From | Action | To | Who |
|---|---|---|---|
| Draft | Send to Distributor | Sent | Hotel, HAT staff |
| Sent | Send Quote (RFQ only) | Quoted | Distributor, HAT staff |
| Sent | Accept Order (Order only) | Accepted | Distributor, HAT staff |
| Sent | Decline | Rejected | Distributor, HAT staff |
| Quoted | Accept Quote / Reject Quote | Accepted / Rejected | Hotel, HAT staff |
| Accepted | Mark Delivered | Delivered | Distributor, HAT staff |
| Delivered | Confirm Receipt | Completed | Hotel, HAT staff |
| Draft, Sent, Quoted | Cancel | Cancelled | Hotel, HAT staff |

## Rules
- Hotel must be in customer group *Hotel*; distributor in supplier group *Distributor*.
- Only one *Active* partnership per distributor–hotel pair.
- A request picks up the partnership active on its date; commission = total × rate %, or the
  fixed amount, or 0 when there is no partnership ⚠.
- Every item needs a rate before a request is Quoted/Accepted.
- Warning (not a block) when the hotel's territory is outside the distributor's coverage.
- A rating may reference a *Completed* request between the same parties; one rating per request.
  Supplier average rating and count update on every rating change.

## Acceptance criteria (verified 2026-10-01 on test data, rolled back)
- [x] Partnership Draft → Active; second active partnership for the same pair is blocked
- [x] Request flows Draft → Completed; quoting without rates is blocked
- [x] 5% partnership on a 15,000 request gives 750 commission
- [x] Out-of-coverage warning shown
- [x] Two ratings (0.8, 0.6) give supplier average 0.7, count 2; duplicate rating blocked
- [ ] Checked in the browser as Hotel and Distributor users

## Open questions
1. **Portal vs desk** — hotels/distributors currently use the desk with restricted roles. Build
   a portal (web pages) for them? *Recommend: yes, next phase.*
2. **Who approves partnerships** — only HAT, or must hotel and distributor accept too?
3. **Commission model** — per order %, fixed fee, membership subscription, or a mix? Who pays
   (distributor or hotel)? When is it invoiced?
4. **Price visibility** — may a hotel see other hotels' prices from the same distributor? (Now: no.)
5. **Directory visibility** — should hotels see all distributor details or only a public profile?
   (Now: full Supplier record is readable.)
6. **Geography** — Albania only, or also Kosovo / North Macedonia / others?
7. **Category names** — source numbering 3.3 → 2.4; "/" replaced by "-" in names
   (ERP-POS, Kuzhine-Bari, Fizike-Teknike); groups added for 4.2 and 5.7 where the source lists items only.
8. **Ordering in ERPNext** — should accepted requests also create Sales/Purchase Orders and
   invoices in ERPNext, or stay as HAT tracking records?

## Out of scope (this version)
Portal UI, email notifications, distributor product catalogues with prices, map/distance search,
commission invoicing.
