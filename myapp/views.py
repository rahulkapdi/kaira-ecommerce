from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import *
from .cart import Cart
from django.db.models import Q
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
import razorpay
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

def send_welcome_email(user):
 
    subject = "Welcome to KAIRA"
 
    html_content = render_to_string(
        "emails/welcome.html",
        {
            "username": user.username,
            "login_url": "http://127.0.0.1:8000/login/",
        }
    )
 
    email = EmailMultiAlternatives(
        subject=subject,
        body="Welcome to KAIRA",
        to=[user.email]
    )
 
    email.attach_alternative(html_content, "text/html")
 
    email.send()


# ── Home ──────────────────────────────────────────────────────────────────────
def home(request):
    categories = Category.objects.all()
    products = Product.objects.filter(is_available=True).order_by('-created_at')[:8]
    best_sellers = Product.objects.filter(is_available=True).order_by('price')[:8]
    return render(request, 'home.html', {
        'categories': categories,
        'products': products,
        'best_sellers': best_sellers,
    })


# ── Shop ──────────────────────────────────────────────────────────────────────
def shop(request):
    products = Product.objects.filter(is_available=True)
    categories = Category.objects.all()
    selected_cat = request.GET.get('category', '')
    sort = request.GET.get('sort', 'newest')
    q = request.GET.get('q', '').strip()

    if selected_cat:
        products = products.filter(category__slug=selected_cat)
    if q:
        products = products.filter(name__icontains=q)
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by('-created_at')

    sort_options = [
        ('newest', 'Newest First'),
        ('price_low', 'Price: Low to High'),
        ('price_high', 'Price: High to Low'),
    ]
    return render(request, 'shop.html', {
        'products': products,
        'categories': categories,
        'selected_cat': selected_cat,
        'sort': sort,
        'q': q,
        'sort_options': sort_options,
    })


# ── Category ──────────────────────────────────────────────────────────────────
def categories_list(request):
    categories = Category.objects.all()
    return render(request, 'categories_list.html', {'categories': categories})


def category_view(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = category.products.filter(is_available=True)
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_low':
        products = products.order_by('price')
    elif sort == 'price_high':
        products = products.order_by('-price')
    else:
        products = products.order_by('-created_at')
    return render(request, 'category.html', {'category': category, 'products': products, 'sort': sort})


# ── Product Detail ────────────────────────────────────────────────────────────
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    related = Product.objects.filter(
        category=product.category, is_available=True
    ).exclude(pk=product.pk)[:4]

    in_wishlist = False
    if request.user.is_authenticated:
        in_wishlist = Wishlist.objects.filter(user=request.user, product=product).exists()

    # Fetch all extra gallery images for this product (ordered by 'order' field)
    gallery_images = product.images.all()

    return render(request, 'product_detail.html', {
        'product': product,
        'related': related,
        'in_wishlist': in_wishlist,
        'gallery_images': gallery_images,
    })


# ═════════════════════════════════════════════════════════════════════════════
#  CART VIEWS
#  These views handle everything to do with the shopping cart.
#  The cart is stored in the session (no database, no login needed).
#
#  URL → view mapping (from urls.py):
#    /cart/                      → cart_view   (show the cart page)
#    /cart/add/<product_id>/     → cart_add    (add an item)
#    /cart/update/<product_id>/  → cart_update (change quantity)
#    /cart/remove/<product_id>/  → cart_remove (delete one item)
#    /cart/clear/                → cart_clear  (empty the whole cart)
# ═════════════════════════════════════════════════════════════════════════════

def cart_view(request):
    """
    Shows the full cart page (/cart/).
    Loads the cart from the session and sends it to the cart.html template.
    """
    # Load the current visitor's cart from their session
    cart = Cart(request)

    # Render cart.html and pass the cart so the template can loop over items
    return render(request, 'cart.html', {'cart': cart})


def cart_add(request, product_id):
    """
    Adds a product to the cart when the 'Add to Cart' button is clicked.

    This view only accepts POST requests (form submissions).
    GET requests (e.g. someone types the URL directly) are ignored.

    After adding, the user is sent back to whatever page they came from.
    """
    # Only process this if the form was submitted (POST), not just a page visit
    if request.method == 'POST':

        # Look up the product in the database; show 404 if it doesn't exist
        product = get_object_or_404(Product, id=product_id)
    
        # Load the cart
        cart = Cart(request)

        # Read the quantity the user typed in the form
        # Default to 1 if nothing was typed or the value wasn't a number
        try:
            qty = int(request.POST.get('quantity', 1))
            # Make sure quantity is at least 1 and not more than stock available
            qty = max(1, min(qty, product.stock))
        except (ValueError, TypeError):
            qty = 1

        # Add the product (and quantity) to the cart
        cart.add(product, quantity=qty)

        # ── Auto-remove from wishlist ────────────────────────────────────────
        # If the user is logged in and this product was in their wishlist,
        # remove it automatically — no need to save it if you're buying it now.
        if request.user.is_authenticated:
            Wishlist.objects.filter(user=request.user, product=product).delete()

        # Show a success message at the top of the next page
        messages.success(request, f'"{product.name}" added to cart.')

        # Figure out which page to go back to after adding
        # The form passes a hidden 'next' field telling us where to go
        next_page = request.POST.get('next', 'product_detail')
        if next_page == 'product_detail':
            # Go back to the product's detail page
            return redirect('product_detail', slug=product.slug)
        # Go back to any other page (e.g. wishlist page)
        return redirect(next_page)

    # If someone visits this URL directly (GET), just send them home
    return redirect('home')


def cart_update(request, product_id):
    """
    Updates the quantity of an item already in the cart.
    Called when the user changes the number in the quantity box and clicks Update.

    If the new quantity is 0, the item is removed from the cart.
    """
    if request.method == 'POST':
        cart = Cart(request)

        # Read the new quantity from the form
        try:
            qty = int(request.POST.get('quantity', 1))
        except (ValueError, TypeError):
            qty = 1

        # Tell the cart to update (the Cart class handles removing if qty=0)
        cart.update(product_id, qty)

    # Always go back to the cart page after updating
    return redirect('cart_view')


def cart_remove(request, product_id):
    """
    Removes a single product from the cart.
    Called when the user clicks the trash/delete icon next to an item.
    """
    if request.method == 'POST':
        cart = Cart(request)
        cart.remove(product_id)   # delete this product from the cart

    # Go back to the cart page
    return redirect('cart_view')


def cart_clear(request):
    """
    Empties the entire cart — removes all items at once.
    Called when the user clicks 'Clear Cart'.
    """
    if request.method == 'POST':
        Cart(request).clear()   # wipe everything

    return redirect('cart_view')


# ═════════════════════════════════════════════════════════════════════════════
#  WISHLIST VIEWS
#  The wishlist saves products a user "hearts" so they can buy later.
#  Unlike the cart, the wishlist IS stored in the database and REQUIRES login.
#
#  URL → view mapping (from urls.py):
#    /wishlist/                      → wishlist_view   (show saved products)
#    /wishlist/toggle/<product_id>/  → wishlist_toggle (add OR remove)
# ═════════════════════════════════════════════════════════════════════════════

@login_required   # If the user is not logged in, send them to the login page
def wishlist_view(request):
    """
    Shows all products the logged-in user has saved to their wishlist.

    select_related('product__category') is a database optimisation —
    it fetches the product AND its category in one query instead of many.
    """
    # Get all wishlist rows for this user from the database
    wishlist_items = Wishlist.objects.filter(
        user=request.user
    ).select_related('product__category')

    # Send the list to wishlist.html so the template can display each item
    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})


@login_required
def wishlist_toggle(request, product_id):
    """
    Adds a product to the wishlist if it isn't there yet.
    Removes it if it's already there.
    This is called a 'toggle' — one button that switches between two states.

    Called when the user clicks the heart (♥) icon on a product.
    """
    # Find the product; show 404 if it doesn't exist
    product = get_object_or_404(Product, id=product_id)

    # get_or_create checks if a Wishlist row already exists for this user+product:
    #   • If it DOESN'T exist → it creates one and returns (obj, True)
    #   • If it DOES exist    → it returns the existing row and (obj, False)
    obj, was_just_created = Wishlist.objects.get_or_create(
        user=request.user,
        product=product
    )

    if was_just_created:
        # The heart was NOT filled before → we just added it → show success
        messages.success(request, f'"{product.name}" added to wishlist.')
    else:
        # The heart WAS already filled → remove it (toggle off)
        obj.delete()
        messages.info(request, f'"{product.name}" removed from wishlist.')

    # Decide where to send the user after toggling
    next_page = request.POST.get('next', 'product_detail')
    if next_page == 'product_detail':
        return redirect('product_detail', slug=product.slug)
    return redirect(next_page)


# ── Auth ──────────────────────────────────────────────────────────────────────
def signup_view(request):
    if request.user.is_authenticated:
        return redirect('login')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
    
        if not username or not email or not password1:
            messages.error(request, 'All fields are required.')
        elif password1 != password2:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
        elif User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
        elif len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password1)
            messages.success(request, f'Welcome, {username}! Account created.')
            send_welcome_email(user)
            return redirect('login')
    return render(request, 'signup.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect(request.GET.get('next', 'home'))
        messages.error(request, 'Invalid username or password.')
    return render(request, 'login.html')


def logout_view(request):
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
def profile_view(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        user = request.user
        if email and email != user.email:
            if User.objects.filter(email=email).exclude(pk=user.pk).exists():
                messages.error(request, 'That email is already in use.')
                return render(request, 'profile.html')
            user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        messages.success(request, 'Profile updated successfully.')
        return redirect('profile')
    return render(request, 'profile.html')


# ── Static pages ──────────────────────────────────────────────────────────────
def about(request):
    team_members = [
        ('Sarah Mitchell', 'Founder & Creative Director', None),
        ('James Okafor', 'Head of Design', None),
        ('Priya Nair', 'Brand Manager', None),
        ('Lucas Chen', 'Head of Operations', None),
    ]
    return render(request, 'about.html', {'team_members': team_members})


def contact(request):
    if request.method == 'POST':
        messages.success(request, 'Thank you! Your message has been sent.')
        return redirect('contact')
    return render(request, 'contact.html')


send_mail(
    subject="SMTP Working",
    message="Congratulations! Your KAIRA SMTP setup is working.",
    from_email=settings.EMAIL_HOST_USER,
    recipient_list=["rahulkapdi7020@gmail.com"],
    fail_silently=False,
)


def test_email(request):
    send_mail(
        subject="SMTP Working",
        message="Congratulations! Your KAIRA SMTP setup is working.",
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=["rahulkapdi7020@gmail.com"],
        fail_silently=False,
    )

    return HttpResponse("Email Sent Successfully!")
def order_history(request):
    return render(request, "order_history.html")


@login_required
def checkout(request):
    cart = Cart(request)

    if len(cart) == 0:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart_view")

    context = {
        "cart": cart,
        "total": cart.get_total(),
    }

    return render(request, "checkout.html", context)

@login_required
def place_order(request):
 
    if request.method != "POST":
        return redirect("checkout")
 
    cart = Cart(request)
 
    if len(cart) == 0:
        messages.error(request, "Your cart is empty.")
        return redirect("cart_view")
 
    payment_method = request.POST.get("payment_method", "cod")
 
    # Create Order
    order = Order.objects.create(
        user=request.user,
        total_price=cart.get_total(),
 
        payment_method=payment_method,
        payment_status="pending",
        order_status="pending",
 
        full_name=request.POST.get("full_name"),
        email=request.POST.get("email"),
        phone=request.POST.get("phone"),
        address=request.POST.get("address"),
        city=request.POST.get("city"),
        state=request.POST.get("state"),
        pincode=request.POST.get("pincode"),
    )
 
    # Create Order Items
    for item in cart:
 
        product = Product.objects.get(id=item["product_id"])
 
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=item["quantity"],
            price=item["price"],
        )
 
        # Reduce Stock
        product.stock -= item["quantity"]
        product.save()
 
    if payment_method == "razorpay":
        # Cart is cleared only after payment is confirmed (see payment_success)
        return redirect("payment_page", order_id=order.id)
 
    # Clear Cart
    cart.clear()
 
    # Send Order Confirmation Email
    send_order_email(order)
 
    messages.success(
        request,
        f"Order #{order.id} placed successfully!"
    )
 
    return redirect("order_success", order_id=order.id)

@login_required
def order_success(request, order_id):
    order = Order.objects.get(id=order_id, user=request.user)

    return render(request, "order_success.html", {
        "order": order
    })

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by("-created_at")

    return render(request, "order_history.html", {
        "orders": orders
    })

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    return render(request, "order_detail.html", {
        "order": order
    })

def send_order_email(order):

    subject = f"Order Confirmation - KAIRA (#{order.id})"

    message = f"""
Hello {order.user.username},

Thank you for shopping with KAIRA!

Your order has been placed successfully.

----------------------------------
Order ID: #{order.id}
Total Amount: ₹{order.total_price}
Payment Method: {order.get_payment_method_display()}
Order Status: {order.get_order_status_display()}
----------------------------------

We will notify you once your order is shipped.

Thank you for choosing KAIRA!

Regards,
KAIRA Team
"""

    send_mail(
        subject,
        message,
        settings.EMAIL_HOST_USER,
        [order.user.email],
        fail_silently=False,
    )

@login_required
def payment_page(request, order_id):

    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user,
        payment_method="razorpay",
        payment_status="pending",
    )

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )

    amount = int(order.total_price * 100)

    payment = client.order.create({
        "amount": amount,
        "currency": "INR",
    })

    order.razorpay_order_id = payment["id"]
    order.save(update_fields=["razorpay_order_id"])

    context = {
        "payment": payment,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "amount": amount,
        "cart_total": order.total_price,
        "order": order,
    }

    print("=================================")
    print("RAZORPAY PAYMENT PAGE")
    print("KEY:", settings.RAZORPAY_KEY_ID)
    print("AMOUNT:", amount)
    print("RAZORPAY ORDER:", payment["id"])
    print("LOCAL ORDER:", order.id)
    print("=================================")

    return render(
        request,
        "payment.html",
        context
    )


@csrf_exempt
@login_required
def payment_success(request):

    print("=================================")
    print("PAYMENT SUCCESS VIEW CALLED")
    print("METHOD:", request.method)
    print("POST:", request.POST)
    print("=================================")

    if request.method != "POST":
        return JsonResponse({
            "status": "error",
            "message": "POST request required"
        }, status=400)


    payment_id = request.POST.get(
        "razorpay_payment_id"
    )

    razorpay_order_id = request.POST.get(
        "razorpay_order_id"
    )

    signature = request.POST.get(
        "razorpay_signature"
    )


    print("Payment ID:", payment_id)
    print("Razorpay Order ID:", razorpay_order_id)
    print("Signature:", signature)


    if not payment_id or not razorpay_order_id or not signature:

        return JsonResponse({
            "status": "error",
            "message": "Missing Razorpay payment information"
        }, status=400)


    order = get_object_or_404(
        Order,
        razorpay_order_id=razorpay_order_id,
        user=request.user,
    )


    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        )
    )


    try:

        client.utility.verify_payment_signature({

            "razorpay_order_id":
                razorpay_order_id,

            "razorpay_payment_id":
                payment_id,

            "razorpay_signature":
                signature,
        })


    except razorpay.errors.SignatureVerificationError:

        print("SIGNATURE VERIFICATION FAILED")

        order.payment_status = "failed"
        order.save(update_fields=["payment_status"])

        return JsonResponse({

            "status": "failed",

            "message":
                "Razorpay signature verification failed."

        }, status=400)


    print("SIGNATURE VERIFIED SUCCESSFULLY")


    order.payment_status = "paid"
    order.order_status = "confirmed"

    order.save(
        update_fields=[
            "payment_status",
            "order_status"
        ]
    )


    # Clear cart only after verified payment
    Cart(request).clear()


    try:
        send_order_email(order)
    except Exception as e:
        print("EMAIL ERROR:", e)


    messages.success(
        request,
        "Payment Successful!"
    )


    redirect_url = reverse(
        "order_success",
        args=[order.id]
    )


    print("REDIRECT:", redirect_url)


    return JsonResponse({

        "status": "success",

        "redirect_url": redirect_url

    })