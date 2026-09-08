# ─────────────────────────────────────────────────────────────────────────────
# cart.py  –  Shopping Cart (stored in the browser session, no login needed)
#
# HOW IT WORKS:
#   Django sessions let us save data on the server tied to a visitor's browser.
#   We store the cart as a Python dictionary inside that session like this:
#
#   session['cart'] = {
#       "5": { "name": "Blue Shirt", "price": "499", "quantity": 2, ... },
#       "12": { "name": "Red Dress",  "price": "999", "quantity": 1, ... },
#   }
#
#   The dictionary KEY is the product ID (as a string).
#   The dictionary VALUE is another dict with the product's details + quantity.
# ─────────────────────────────────────────────────────────────────────────────


class Cart:
    """
    A simple shopping cart saved in the user's session.
    Works for both logged-in users and guests (no account needed).
    """

    # ── Step 1: Load the cart when a page is opened ───────────────────────────
    def __init__(self, request):
        """
        Called automatically every time we write  Cart(request)  in a view.
        It either loads the existing cart from the session, or creates a new
        empty one if the visitor has never had a cart before.
        """
        # Save a reference to the session so we can read/write it later
        self.session = request.session

        # Try to get the existing cart dictionary from the session
        cart = self.session.get('cart')

        # If no cart exists yet (first visit or cleared), create an empty one
        if not cart:
            cart = {}
            self.session['cart'] = cart   # save the empty dict in the session

        # Store the cart dict on self so other methods can use it
        self.cart = cart

    # ── Step 2: Add a product to the cart ────────────────────────────────────
    def add(self, product, quantity=1):
        """
        Adds a product to the cart, or increases its quantity if it's
        already there.  quantity cannot go above the available stock.
        """
        # Use the product's ID as the key (must be a string for JSON sessions)
        product_id = str(product.id)

        # If this product is NOT in the cart yet, add a fresh entry
        if product_id not in self.cart:
            self.cart[product_id] = {
                'name':     product.name,
                'price':    str(product.price),   # stored as string to be safe
                'slug':     product.slug,
                'quantity': 0,                    # we'll add the real qty below
                'image':    product.image.url if product.image else None,
                'category': product.category.name,
            }

        # Work out the new total quantity (existing + what was just added)
        new_quantity = self.cart[product_id]['quantity'] + quantity

        # Never let the quantity go above the stock available
        if new_quantity > product.stock:
            new_quantity = product.stock

        self.cart[product_id]['quantity'] = new_quantity

        # Tell Django the session has changed so it saves it
        self._save()

    # ── Step 3: Update the quantity of a product already in the cart ─────────
    def update(self, product_id, quantity):
        """
        Changes how many of a product the user wants.
        If quantity is set to 0 (or less), the product is removed.
        """
        product_id = str(product_id)

        # Only do something if the product is actually in the cart
        if product_id in self.cart:
            if quantity > 0:
                # Update to the new quantity
                self.cart[product_id]['quantity'] = quantity
            else:
                # Quantity is 0 — remove the item completely
                del self.cart[product_id]

            self._save()

    # ── Step 4: Remove a single product from the cart ────────────────────────
    def remove(self, product_id):
        """Deletes one product from the cart entirely."""
        product_id = str(product_id)

        if product_id in self.cart:
            del self.cart[product_id]
            self._save()

    # ── Step 5: Empty the entire cart ────────────────────────────────────────
    def clear(self):
        """Removes ALL items from the cart (e.g. after checkout)."""
        self.session.pop('cart', None)   # delete the 'cart' key from the session
        self._save()

    # ── Helper: Tell Django to save the session ───────────────────────────────
    def _save(self):
        """
        Django only auto-saves the session if it was modified.
        Setting session.modified = True forces it to save every time.
        """
        self.session.modified = True

    # ── Step 6: Loop over cart items in templates  ({% for item in cart %}) ──
    def __iter__(self):
        """
        Allows us to loop over the cart in Django templates like:
            {% for item in cart %}
                {{ item.name }}  –  ₹{{ item.price }}
            {% endfor %}

        For each item we also calculate the line total (price × quantity).
        """
        for product_id, item in self.cart.items():
            # Build a copy of the item dict and add calculated fields
            cart_item = item.copy()
            cart_item['product_id'] = product_id
            cart_item['total'] = round(float(item['price']) * item['quantity'], 2)
            yield cart_item

    # ── Step 7: Count total items  (used for the cart badge in the navbar) ───
    def __len__(self):
        """
        Returns the TOTAL number of items in the cart (counting quantities).
        Example: 2 shirts + 1 dress = 3
        Used by {{ cart_count }} in templates.
        """
        total_items = 0
        for item in self.cart.values():
            total_items += item['quantity']
        return total_items

    # ── Step 8: Calculate the grand total price ───────────────────────────────
    def get_total(self):
        """
        Returns the total cost of everything in the cart.
        Example: 2 × ₹499  +  1 × ₹999  =  ₹1997
        Used by {{ cart_total }} in templates.
        """
        grand_total = 0
        for item in self.cart.values():
            price     = float(item['price'])
            quantity  = item['quantity']
            grand_total += price * quantity

        return round(grand_total, 2)
