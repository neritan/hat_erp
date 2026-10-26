# Hotel Cart — Review and Check Out Marketplace Orders

Status: **built** (2026-10-23) on branch `feat/hotel-cart` — awaiting HAT review. Builds on
[marketplace.md](marketplace.md).

## Goal
Until now *Add to Order* silently put each product into a Draft order per distributor, and the
hotel had to find and send each draft by hand. The button is now **Add to Cart** everywhere
(marketplace offers, listing form and list), including offers priced on request. The cart gives the hotel one place to review
everything it has picked on the marketplace — grouped by distributor, with quantities, prices and
totals — and to place all its orders in one go (**Place Order**; there is no payment step yet).

## Decisions (HAT, 2026-10-23)
| Topic | Decision |
|---|---|
| Owner | **Shared per hotel**: every user of the hotel sees and fills the same cart |
| Distributor minimum order | **Warn only**: below *Minimum Order* the hotel is warned but can still send |
| Place Order | **All distributors at once**, with *Order only this* per distributor |

## How it works
- The cart is the hotel's **Draft HAT Order Requests** (one per distributor), so nothing new is
  stored and the order workflow, partner prices and commission are unchanged.
- **Cart page** (`/desk/hat-cart`, sidebar *Cart*, *Cart (n)* button on the Marketplace): one card
  per distributor with its lines (product, unit price, quantity, amount), subtotal and minimum
  order status; quantities can be changed and lines removed (a distributor with no lines left
  disappears from the cart). HAT staff pick the hotel.
- **Place Order** asks once for *Delivery needed by*, *Delivery address* (the hotel's addresses) and
  notes, then runs *Send to Distributor* on every draft. Each distributor's part succeeds or fails
  on its own (e.g. a listing below its minimum quantity) and the result lists both.
- Below a distributor's *Minimum Order*: orange warning on the cart card and when placing the order, and an
  alert when the order is sent from its own form.

## Rules
- Line quantity must still meet the listing's minimum quantity (existing rule).
- Out-of-stock or unpublished listings are flagged on the cart line (existing warning on send).
- Only drafts are in the cart; sent orders follow the normal workflow.

## Acceptance criteria
- [x] Two users of the same hotel see the same cart; another hotel's user does not
- [x] Cart groups lines by distributor with subtotals and grand total; count matches lines
- [x] Changing quantity updates amount and totals; quantity 0 / remove deletes the line; last line removes the draft
- [x] Below minimum order → warning, the order is still sent
- [x] Place Order sends every draft (status Sent) with delivery date, address and notes; *Order only this* sends one
- [x] A failing distributor part (below listing minimum qty) is reported; the others are still sent
- [x] Automated: `hat/tests/test_cart.py` (13 tests — shared cart, cross-hotel access, totals/count,
  quantity and removal, minimum quantity and minimum order, partial failure, unexpected and database
  errors, single-distributor order, empty cart, unavailable lines, constant query count)
- [ ] Checked in the browser as a Hotel user

## Out of scope
Saved carts / templates for repeat orders, scheduled (recurring) orders, payment / checkout.
