# Price on Quantity (volume pricing on listings)

## Goal
Distributors often sell cheaper per unit when a hotel buys more. A third price type on a
marketplace listing, **Price on Quantity**, lets a distributor publish a price per quantity range,
so hotels see the volume discount up front and orders carry the right unit price without a
quote round-trip.

## Actors & permissions
| Actor | Can see | Can do |
|---|---|---|
| Distributor | own listings | choose the price type; enter and change the quantity ranges of own listings |
| Hotel | ranges of published listings of verified distributors | order any quantity; the unit price follows the quantity |
| HAT staff | all listings | everything distributors can, on any listing |

The ranges are public like the Fixed Price is. A partner hotel's discounted price stays private
to that hotel (unchanged rule).

## User stories
- As a distributor, I want to give a lower unit price from 10 and from 50 units, so that hotels
  order larger quantities.
- As a hotel, I want to see the price for each quantity range on the marketplace, so that I can
  decide how much to order.
- As a hotel, I want the cart to update the unit price when I change the quantity.

## Data model
- `HAT Listing.price_type`: options **Fixed Price**, **Price on Request**, **Price on Quantity**.
- New child table **HAT Listing Price Tier** (`HAT Listing.price_tiers`), shown only for
  Price on Quantity:
  | Field | Type | Notes |
  |---|---|---|
  | `from_qty` | Float, required | the range starts here and ends where the next row starts; the last row is open-ended |
  | `price` | Currency (ALL), required | public price per unit in this range |
- For Price on Quantity, `HAT Listing.price` is set to the first range's price and
  `minimum_qty` to the first range's From quantity (both read-only results, kept for lists,
  sorting and the existing minimum-order check).

## Rules
1. **One price for the whole quantity**: the unit price is the price of the range the ordered
   quantity falls in (60 units with "50+: 950" → 60 × 950).
2. **Partnership discount on top**: the range price, less the partnership discount when the
   partnership covers the listing's category (same as Fixed Price).
3. Validation: at least one row; every From quantity > 0; no two rows with the same From
   quantity; every price > 0. Rows are sorted by From quantity on save.
4. Ordering below the first From quantity is blocked by the existing minimum-order rule.
5. **Order requests**: a Price on Quantity line is re-priced from its quantity whenever a Draft
   order request is saved (add to cart, cart quantity change, edits). Once sent, prices stay.
   An order request made of Fixed Price and Price on Quantity lines is an **Order**; any
   Price on Request line still makes it a **Request for Quotation**.
6. **Marketplace**: the card shows "from <lowest price>" and the ranges; the *Best price* badge
   compares the price at each offer's minimum order. The *Add to Cart* dialog shows the ranges
   and the unit and total price for the quantity typed.
7. **Quotes**: when a distributor starts a quote, a Price on Quantity listing pre-fills the
   price for the requested quantity.
8. No commission change: commission is computed on the order amount as today.

## Acceptance criteria
- [ ] A listing can be saved with Price on Quantity and 1+ ranges; invalid ranges are refused
      with a clear message.
- [ ] Minimum order and the listed price follow the first range automatically.
- [ ] Adding 5, 10, 60 units of a 1/10/50 listing gives unit prices 1,200 / 1,100 / 950.
- [ ] A partner hotel with 10 % discount gets 990 for 10 units.
- [ ] Changing the quantity in the cart re-prices the line.
- [ ] The marketplace card and the Add to Cart dialog show the ranges.
- [ ] Fixed Price and Price on Request behave exactly as before.

## Open questions
None blocking. Later: show the saving vs. the first range in the cart.

## Out of scope
Price per hotel, EUR, ranges by order value instead of quantity.
