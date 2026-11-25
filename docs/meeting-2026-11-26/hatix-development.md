# Hatix: development update

*Meeting 26 Nov 2026 · work from 1 Oct to 25 Nov 2026 · 11 pull requests merged to `dev`*

## In one line
Hotels can find products, compare distributors, order through a shared cart or ask for sealed quotes. Distributors fulfil orders and quotes. HAT staff follow everything through five reports. Everything runs on the dev server with real products from four distributors.

## What is built

### Marketplace and ordering
- **Marketplace**: hotels browse every verified distributor's products. They can search, filter by category or distributor, and open a product page that compares all distributor offers and prices.
- **Three price types**: Fixed Price, Price on Request, and Price on Quantity (price bands by quantity).
- **Hotel cart**: one shared cart per hotel with one draft order per distributor. The hotel sends everything at once or one distributor at a time. A minimum-order warning appears but never blocks the order.
- **Order requests**: an order goes from the hotel to the distributor through a workflow (Sent → … → Completed).
- **Partner prices**: a distributor's partnership with HAT discounts its prices automatically.

### Quote requests (reverse marketplace)
- A hotel publishes a request for one or more products with a deadline.
- Verified distributors in the matching categories are notified. They send **sealed** quotes, pre-priced from their listings.
- The hotel compares the quotes and **awards each product line** separately. Each winning distributor gets its own order.
- Requests close automatically at their deadline.

### Profiles and reviews
- **Read-only profile tabs** on the Customer (hotel) and Supplier (distributor) forms.
- **Distributors** see every hotel, but only their own dealings with it.
- **Hotels** see verified distributors. A hotel rates each completed order and writes one overall review per distributor.

### Roles, access and privacy
- **One structure per user**: every hotel or distributor user belongs to exactly one hotel or one distributor, chosen on the User form. The matching access permission is created automatically.
- **Partnerships are HAT ↔ distributor only**:
  - Hotels see their final price only.
  - They never see the partnership, the public price it discounts, or HAT's commission (forms, cart, reports, dashboard cards).
- **Distributors cannot place orders.** They only fulfil them.
- **Hotel and distributor users** see only the Hatix area. HAT staff keep the full system.

### Reports for HAT staff
- Daily Activities
- Orders by Hotel
- Product Catalogue
- Quote Requests
- Sales by Distributor (commission is hidden from hotels)

### Brand and platform
- Rebranded to **Hatix**: logos, icons, and Hatix as the home page after login.
- **Files and pictures in S3 object storage** (Hetzner), served through short-lived private links.
- Works on the Frappe 16 server and on Frappe 17 locally.

### Data on the dev server
| Distributor | Products |
|---|---|
| Ed Frozen | 274 |
| Bontrade (Ronnefeldt) | 15 |
| Nurellari | 9 |
| Salto | 5 |

- In total there are 303 items and 4 hotels. An import script loads a distributor's catalogue, pictures and prices, and is safe to run again.
- **15 demo users**: one for each distributor (11) and each hotel (4). The logins are in `/opt/hat-dev/demo-users.txt` on the server.

### Recent fixes (this week)
- Placing orders through the API, and the cart's **Send** button for a single distributor.
- The quote's product dropdown showed the full product description; it is now shortened.
- Earlier fixes: Submit Quote did nothing on an unchanged form; distributor search and Supplier list permissions for hotels.

### Quality
- **61 automated tests** cover the cart, quotes, permissions, privacy, reports, user structure and navigation.

## To discuss / decide
1. **Product Catalogue report**: should hotels see *their own* price, or the public price as today?
2. **The same dropdown fix for Hatix Listing**: the product field there still shows long descriptions.
3. **Email is not set up**: "Reset Password", welcome emails and notifications by email do not go out. We need an SMTP account (which address?).
4. **Demo passwords follow a pattern** (`<name>@4321`): change them before anyone outside the team uses the accounts.
5. **Unverified distributors**: ALTA GROUP and BIANCO MEDITERRANEO COMPANY have users, but their products stay hidden until HAT verifies them.
6. **Data clean-up**:
   - 83 Ed Frozen products have no picture.
   - The hotel record "Yaht Hotel" should be spelled "Yacht Hotel".
7. **Next distributors to import**: whose catalogues do we have?
