import os
import json
import random
import uuid
from datetime import datetime, timedelta 
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message as EmailMessage
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, text
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai 



app = Flask(__name__)

# ==========================================
# 🛠️ LOCAL DEVELOPMENT CONFIGURATIONS
# ==========================================
app.config['SECRET_KEY'] = 'aivaro_secret_premium_v1_secure_key_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 🔥 ANTI-CACHE MAGIC
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# 🔥 UPLOAD FOLDERS
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['CHAT_UPLOAD_FOLDER'] = 'static/chat_images' 
app.config['PAYMENT_UPLOAD_FOLDER'] = 'static/payment_proofs'
app.config['REVIEW_UPLOAD_FOLDER'] = 'static/review_images'

# EMAIL CONFIG
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'aivaroclothing7@gmail.com' 
app.config['MAIL_PASSWORD'] = 'rpsjzveijqqacyhu' 
mail = Mail(app)

app.config['GEMINI_API_KEY'] = 'YOUR_GEMINI_API_KEY_HERE' 

for folder in [app.config['UPLOAD_FOLDER'], app.config['CHAT_UPLOAD_FOLDER'], app.config['PAYMENT_UPLOAD_FOLDER'], app.config['REVIEW_UPLOAD_FOLDER']]:
    if not os.path.exists(folder): os.makedirs(folder)

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# 🗄️ DATABASE MODELS
# ==========================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(200))
    dob = db.Column(db.String(20), nullable=True)
    bday_code = db.Column(db.String(20), nullable=True)
    bday_discount = db.Column(db.Integer, nullable=True)
    bday_year = db.Column(db.Integer, nullable=True)
    is_admin = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    
    def set_password(self, password): 
        self.password_hash = generate_password_hash(password)
    def check_password(self, password): 
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), nullable=False)
    gender = db.Column(db.String(20), default='Men')
    description = db.Column(db.Text, nullable=False)
    sizes = db.Column(db.String(100)) 
    size_chart = db.Column(db.Text, nullable=True)
    stock = db.Column(db.Integer, default=0)
    weight = db.Column(db.Float, default=0.5)
    is_luxury = db.Column(db.Boolean, default=False)
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")
    reviews = db.relationship('Review', backref='product', lazy=True, cascade="all, delete-orphan")
    
    @property
    def final_price(self):
        if self.discount > 0: return int(self.price - (self.price * self.discount / 100))
        return int(self.price)
    
    def get_size_chart(self):
        if self.size_chart: return json.loads(self.size_chart)
        return {}

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(200), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    size = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    delivery_charge = db.Column(db.Float, default=0.0) 
    discount_amount = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, nullable=False)
    applied_coupon = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='Pending')
    date_ordered = db.Column(db.DateTime, default=datetime.now)
    payment_method = db.Column(db.String(50), default='COD')
    payment_gateway = db.Column(db.String(50), nullable=True)
    trx_id = db.Column(db.String(100), nullable=True)
    payment_screenshot = db.Column(db.String(200), nullable=True)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    product_size = db.Column(db.String(50))
    product_image = db.Column(db.String(200))
    quantity = db.Column(db.Integer, nullable=False)

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=True) 
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    image_url = db.Column(db.String(200), nullable=True) 
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User', backref='reviews')

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=False)
    min_spend = db.Column(db.Float, nullable=False)
    active = db.Column(db.Boolean, default=True)

class Banner(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image_url = db.Column(db.String(200), nullable=False)

class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

# ==========================================
# 🛠️ DELIVERY & DISCOUNT CALCULATION
# ==========================================
def merge_cart_after_login(user):
    if 'cart' in session:
        guest_cart = session['cart']
        for item in guest_cart:
            if 'product_id' in item:
                existing = CartItem.query.filter_by(user_id=user.id, product_id=item['product_id'], size=item.get('size', 'M')).first()
                if existing: existing.quantity += item.get('quantity', 1)
                else: db.session.add(CartItem(user_id=user.id, product_id=item['product_id'], size=item.get('size', 'M'), quantity=item.get('quantity', 1)))
        db.session.commit()
        session.pop('cart', None)

# 🔥 UPDATED LOGIC FOR DHAKA / SUB-URBAN / OTHERS
def calculate_order_total(base_price, division, applied_coupon_code):
    discount_amount = 0
    div_lower = str(division).lower()
    
    # Check Delivery Region
    if 'sub-urban' in div_lower or 'sub urban' in div_lower:
        delivery_charge = 100
    elif 'dhaka' in div_lower:
        delivery_charge = 80
    else:
        delivery_charge = 130
    
    # Check Discounts
    if applied_coupon_code and current_user.is_authenticated and current_user.bday_code and applied_coupon_code == current_user.bday_code:
        discount_amount = int((base_price * (current_user.bday_discount or 0)) / 100)
    elif applied_coupon_code:
        coupon = Coupon.query.filter_by(code=applied_coupon_code.upper(), active=True).first()
        if coupon and base_price >= coupon.min_spend:
            discount_amount = int((base_price * coupon.discount_percent) / 100)
            
    final_total = (base_price - discount_amount) + delivery_charge
    return final_total, discount_amount, delivery_charge

@app.before_request
def check_banned_user():
    if request.endpoint and 'static' in request.endpoint: return
    if current_user.is_authenticated and getattr(current_user, 'is_banned', False):
        logout_user()
        flash('Your account has been banned.', 'error')
        return redirect(url_for('login'))

@app.context_processor
def inject_global_data():
    data = {'cart_count': 0, 'is_birthday': False, 'bday_code': '', 'bday_discount': 0}
    if current_user.is_authenticated:
        items = CartItem.query.filter_by(user_id=current_user.id).all()
        data['cart_count'] = sum(item.quantity for item in items if item.product is not None)
        if current_user.dob:
            try:
                dob_date = datetime.strptime(current_user.dob, '%Y-%m-%d')
                today = datetime.now()
                if dob_date.month == today.month and dob_date.day == today.day:
                    data['is_birthday'] = True
                    current_year = today.year
                    if not current_user.bday_code or current_user.bday_year != current_year:
                        current_user.bday_code = f"BDAY-{random.randint(1000, 9999)}"
                        current_user.bday_discount = random.randint(15, 30) 
                        current_user.bday_year = current_year
                        db.session.commit()
                    data['bday_code'] = current_user.bday_code
                    data['bday_discount'] = current_user.bday_discount
            except: pass
    else:
        valid_count = sum(item.get('quantity', 1) for item in session.get('cart', []) if Product.query.get(item.get('product_id')))
        data['cart_count'] = valid_count
    return data

@app.context_processor
def inject_active_coupon():
    try: return dict(coupon=Coupon.query.filter_by(active=True).order_by(Coupon.id.desc()).first())
    except Exception: return dict(coupon=None)

# ==========================================
# 🛍️ PUBLIC ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template('home.html', products=Product.query.order_by(Product.id.desc()).all(), banners=Banner.query.all())

@app.route('/shop')
def shop():
    category = request.args.get('category', 'All')
    gender = request.args.get('gender', 'All')
    search_query = request.args.get('q')
    size_filter = request.args.get('size', 'All')
    min_price = request.args.get('min_price', type=int)
    max_price = request.args.get('max_price', type=int)
    
    query = Product.query
    if gender != 'All': query = query.filter(Product.gender.ilike(f'{gender}'))
    if category != 'All': query = query.filter(Product.category.ilike(f'%{category}%'))
    if size_filter != 'All': query = query.filter(Product.sizes.ilike(f'%{size_filter}%'))
    if min_price: query = query.filter(Product.price >= min_price)
    if max_price: query = query.filter(Product.price <= max_price)
    if search_query: query = query.filter(or_(Product.name.ilike(f'%{search_query}%'), Product.category.ilike(f'%{search_query}%')))
    
    sort_by = request.args.get('sort')
    if not sort_by or sort_by not in ['price_asc', 'price_desc']: query = query.order_by(Product.id.desc())
    products = query.all()
    if sort_by == 'price_asc': products.sort(key=lambda x: x.final_price)
    elif sort_by == 'price_desc': products.sort(key=lambda x: x.final_price, reverse=True)
    
    luxury_products = Product.query.filter_by(is_luxury=True).order_by(Product.id.desc()).all()
    unique_categories = [r[0] for r in db.session.query(Product.category).distinct().all() if r[0]]
    
    return render_template('shop.html', products=products, luxury_products=luxury_products, banners=Banner.query.all(), categories=unique_categories, current_category=category, current_gender=gender)

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if len(q) < 2: return jsonify([])
    results = Product.query.filter(or_(Product.name.ilike(f'%{q}%'), Product.category.ilike(f'%{q}%'))).limit(5).all()
    return jsonify([{'id': p.id, 'name': p.name, 'price': p.final_price, 'image': p.images[0].image_url if p.images else ''} for p in results])

@app.route('/top-selling')
def top_selling():
    all_products = Product.query.all()
    ranked_products = []
    for p in all_products:
        sold_count = 0
        order_items = OrderItem.query.filter_by(product_id=p.id).all()
        for item in order_items:
            if item.order and item.order.status != 'Cancelled': sold_count += item.quantity
        ranked_products.append({'product': p, 'sold': sold_count})
    ranked_products.sort(key=lambda x: x['sold'], reverse=True)
    return render_template('top_selling.html', ranked_products=ranked_products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    reviews = Review.query.filter_by(product_id=product_id).order_by(Review.created_at.desc()).all()
    related = Product.query.filter(Product.category == product.category, Product.id != product.id).limit(4).all()
    return render_template('product.html', product=product, reviews=reviews, related_products=related)

@app.route('/contact')
def contact(): return render_template('contact.html')
@app.route('/about')
def about(): return render_template('about.html')
@app.route('/terms')
def terms(): return render_template('terms.html')

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        name = request.form.get('name'); email = request.form.get('email'); message = request.form.get('message')
        db.session.add(Feedback(name=name, email=email, message=message)); db.session.commit()
        flash('Thank you! Your feedback has been submitted.', 'success')
        return redirect(url_for('feedback'))
    return render_template('feedback.html')

# ==========================================
# 🔐 AUTH & ACCOUNT ROUTES
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            if getattr(user, 'is_banned', False):
                flash('Your account has been banned.', 'error'); return redirect(url_for('login'))
            login_user(user); merge_cart_after_login(user)
            flash(f'Welcome back, {user.name.split()[0]}!', 'success')
            return redirect(url_for('checkout') if request.args.get('next') == 'checkout' else url_for('admin_dashboard' if user.is_admin else 'home'))
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form.get('email'); phone = request.form.get('phone', '')
        if User.query.filter(or_(User.email == email, User.phone == phone)).first():
            flash('Email or Phone already exists.', 'error'); return redirect(url_for('login'))
        otp = random.randint(1000, 9999)
        session['temp_user'] = { 'name': request.form['name'], 'email': email, 'phone': phone, 'password': request.form['password'], 'otp': otp, 'expiry': (datetime.now() + timedelta(minutes=2)).timestamp() }
        try:
            msg = EmailMessage('AIVARO Verification', sender=app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f"Your OTP is: {otp}"; mail.send(msg)
        except: pass
        return redirect(url_for('verify_otp'))
    return render_template('signup.html')
# ==========================================
# 🔑 FORGOT & RESET PASSWORD ROUTES
# ==========================================
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            otp = random.randint(1000, 9999)
            session['reset_email'] = email
            session['reset_otp'] = otp
            try:
                msg = EmailMessage('AIVARO Password Reset', sender=app.config['MAIL_USERNAME'], recipients=[email])
                msg.body = f"Your Password Reset OTP is: {otp}\n\nPlease do not share this code with anyone."
                mail.send(msg)
            except:
                pass
            flash('An OTP has been sent to your email.', 'success')
            return redirect(url_for('verify_reset_otp'))
        else:
            flash('No account found with that email address.', 'error')
    return render_template('forgot_password.html')

@app.route('/verify-reset-otp', methods=['GET', 'POST'])
def verify_reset_otp():
    if 'reset_email' not in session: return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        if user_otp and int(user_otp) == session.get('reset_otp'):
            flash('OTP Verified! Please enter your new password.', 'success')
            return redirect(url_for('reset_password'))
        else:
            flash('Invalid or expired OTP. Try again.', 'error')
    return render_template('verify_reset_otp.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_email' not in session: return redirect(url_for('login'))
    if request.method == 'POST':
        new_password = request.form.get('password')
        # confirm_password may be passed if your form has it, otherwise we just set the new password
        confirm_password = request.form.get('confirm_password', new_password) 
        
        if new_password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('reset_password'))
            
        user = User.query.filter_by(email=session['reset_email']).first()
        if user:
            user.set_password(new_password)
            db.session.commit()
            session.pop('reset_email', None)
            session.pop('reset_otp', None)
            flash('Password reset successfully! You can now log in.', 'success')
            return redirect(url_for('login'))
    return render_template('reset_password.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if 'temp_user' not in session: return redirect(url_for('signup'))
    if request.method == 'POST':
        if datetime.now().timestamp() > session['temp_user'].get('expiry', 0):
            flash('Your OTP has expired!', 'error'); return redirect(url_for('verify_otp'))
        if int(request.form['otp']) == session.get('temp_user', {}).get('otp'):
            d = session['temp_user']
            u = User(name=d['name'], email=d['email'], phone=d.get('phone', ''))
            u.set_password(d['password'])
            db.session.add(u); db.session.commit(); login_user(u); merge_cart_after_login(u)
            session.pop('temp_user', None)
            flash(f'Welcome to AIVARO!', 'success'); return redirect(url_for('home'))
        flash('Invalid OTP!', 'error')
    return render_template('verify_otp.html')

@app.route('/logout')
@login_required
def logout(): logout_user(); return redirect(url_for('home'))

# ==========================================
# 🛒 CART & CHECKOUT
# ==========================================
@app.route('/api/add-to-cart', methods=['POST'])
def api_add_to_cart():
    data = request.json; product = Product.query.get(data['product_id'])
    if not product: return jsonify({'status': 'error', 'message': 'Product not found'})
    if current_user.is_authenticated:
        existing = CartItem.query.filter_by(user_id=current_user.id, product_id=data['product_id'], size=data['size']).first()
        if existing: existing.quantity += 1
        else: db.session.add(CartItem(user_id=current_user.id, product_id=data['product_id'], size=data['size'], quantity=1))
        db.session.commit()
    else:
        cart = session.get('cart', []); found = False
        for i in cart:
            if i['product_id'] == data['product_id'] and i['size'] == data['size']: i['quantity'] += 1; found = True; break
        if not found: cart.append({'product_id': data['product_id'], 'size': data['size'], 'quantity': 1})
        session['cart'] = cart; session.modified = True
    total = sum(i.quantity for i in CartItem.query.filter_by(user_id=current_user.id).all()) if current_user.is_authenticated else sum(i['quantity'] for i in session.get('cart', []))
    return jsonify({'status': 'success', 'total_items': total})

@app.route('/api/update-cart', methods=['POST'])
def api_update_cart():
    data = request.json; cart_id = int(data['cart_id']); action = data['action']
    if current_user.is_authenticated:
        item = CartItem.query.get(cart_id)
        if item:
            if action == 'increase': item.quantity += 1
            elif action == 'decrease': 
                item.quantity -= 1
                if item.quantity < 1: db.session.delete(item)
            db.session.commit()
    else:
        cart = session.get('cart', [])
        if 0 <= cart_id < len(cart):
            if action == 'increase': cart[cart_id]['quantity'] += 1
            elif action == 'decrease':
                cart[cart_id]['quantity'] -= 1
                if cart[cart_id]['quantity'] < 1: cart.pop(cart_id)
            session['cart'] = cart; session.modified = True
    return jsonify({'status': 'success'})

@app.route('/api/get-cart')
def api_get_cart():
    items = []; total = 0
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        for i in cart_items:
            if i.product: 
                items.append({'cart_id': i.id, 'product_id': i.product.id, 'name': i.product.name, 'price': i.product.final_price, 'size': i.size, 'quantity': i.quantity, 'image': i.product.images[0].image_url if i.product.images else ''})
                total += i.product.final_price * i.quantity
            else: db.session.delete(i)
        db.session.commit()
    else:
        cart = session.get('cart', []); valid_cart = []
        for idx, i in enumerate(cart):
            p = Product.query.get(i.get('product_id'))
            if p: 
                items.append({'cart_id': len(valid_cart), 'product_id': p.id, 'name': p.name, 'price': p.final_price, 'size': i['size'], 'quantity': i['quantity'], 'image': p.images[0].image_url if p.images else ''})
                total += p.final_price * i['quantity']; valid_cart.append(i)
        if len(valid_cart) != len(cart): session['cart'] = valid_cart; session.modified = True
    return jsonify({'items': items, 'total': total})

@app.route('/api/remove-item', methods=['POST'])
def api_remove_item():
    if current_user.is_authenticated: CartItem.query.filter_by(id=request.json['cart_id']).delete(); db.session.commit()
    else: c = session.get('cart', []); del c[int(request.json['cart_id'])]; session['cart'] = c; session.modified = True
    return jsonify({'status': 'success'})

@app.route('/api/apply-coupon', methods=['POST'])
def api_apply_coupon():
    data = request.get_json(); code = data.get('code', '').strip().upper(); cart_total = float(data.get('cart_total', 0))
    if current_user.is_authenticated and current_user.bday_code and code == current_user.bday_code:
        return jsonify({'success': True, 'discount_percent': current_user.bday_discount})
    coupon = Coupon.query.filter_by(code=code, active=True).first()
    if not coupon: return jsonify({'success': False, 'message': 'Invalid or expired coupon.'})
    if cart_total < coupon.min_spend: return jsonify({'success': False, 'message': f'Minimum spend of ৳ {coupon.min_spend} required.'})
    return jsonify({'success': True, 'discount_percent': coupon.discount_percent})

@app.route('/cart')
def cart(): return render_template('cart.html')

# 🔥 GUEST CHECKOUT
@app.route('/checkout', methods=['GET'])
def checkout():
    formatted_items = []; subtotal = 0
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        for item in cart_items:
            if item.product:
                formatted_items.append({'product_id': item.product.id, 'name': item.product.name, 'price': item.product.final_price, 'size': item.size, 'quantity': item.quantity, 'image': item.product.images[0].image_url if item.product.images else ''})
                subtotal += item.product.final_price * item.quantity
    else:
        cart = session.get('cart', [])
        for item in cart:
            p = Product.query.get(item.get('product_id'))
            if p:
                formatted_items.append({'product_id': p.id, 'name': p.name, 'price': p.final_price, 'size': item['size'], 'quantity': item['quantity'], 'image': p.images[0].image_url if p.images else ''})
                subtotal += p.final_price * item['quantity']
                
    if not formatted_items: return redirect(url_for('shop'))
    return render_template('checkout.html', total_price=subtotal, cart_items=formatted_items)

# 🔥 GUEST ORDER PLACEMENT
@app.route('/place-order', methods=['POST'])
def place_order():
    formatted_items = []; valid_items = []
    
    if current_user.is_authenticated:
        cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
        valid_items = [item for item in cart_items if item.product]
    else:
        cart = session.get('cart', [])
        for i in cart:
            p = Product.query.get(i.get('product_id'))
            if p: valid_items.append({'product': p, 'size': i['size'], 'quantity': i['quantity']})

    if not valid_items: return redirect(url_for('shop'))
    
    form_data = request.form
    subtotal = sum(item.product.final_price * item.quantity for item in valid_items) if current_user.is_authenticated else sum(item['product'].final_price * item['quantity'] for item in valid_items)
    
    applied_coupon = form_data.get('applied_coupon')
    division = form_data.get('division', '')
    district = form_data.get('district', '')
    
    # Calculate order total using Division
    final_total, discount_amount, delivery_charge = calculate_order_total(subtotal, division, applied_coupon)
    
    payment_method = form_data.get('payment_method'); trx_id = form_data.get('trx_id'); payment_gateway = form_data.get('payment_gateway')
    screenshot_filename = None
    
    if payment_method == 'Online' and 'payment_screenshot' in request.files:
        file = request.files['payment_screenshot']
        if file:
            screenshot_filename = secure_filename(f"pay_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['PAYMENT_UPLOAD_FOLDER'], screenshot_filename))

    new_order = Order(
        user_id=current_user.id if current_user.is_authenticated else None, 
        customer_name=form_data.get('name'), address=f"{form_data.get('address')}, {district}, {division}", 
        phone=form_data.get('phone'), total_price=final_total, delivery_charge=delivery_charge, discount_amount=discount_amount, applied_coupon=applied_coupon,
        payment_method=payment_method, payment_gateway=payment_gateway, trx_id=trx_id, payment_screenshot=screenshot_filename
    )
    db.session.add(new_order); db.session.flush() 
    
    for item in valid_items: 
        p = item.product if current_user.is_authenticated else item['product']
        sz = item.size if current_user.is_authenticated else item['size']
        qty = item.quantity if current_user.is_authenticated else item['quantity']
        db.session.add(OrderItem(order_id=new_order.id, product_id=p.id, product_name=p.name, product_price=p.final_price, product_size=sz, product_image=p.images[0].image_url if p.images else '', quantity=qty))
    
    if current_user.is_authenticated: CartItem.query.filter_by(user_id=current_user.id).delete()
    else: session.pop('cart', None)
    
    db.session.commit()
    return redirect(url_for('order_success', order_id=new_order.id))

@app.route('/buy-now', methods=['POST'])
def buy_now():
    product = Product.query.get_or_404(request.form.get('product_id'))
    qty = int(request.form.get('quantity', 1))
    division = request.form.get('division', '')
    district = request.form.get('district', '')
    applied_coupon = request.form.get('applied_coupon')
    
    subtotal = product.final_price * qty
    final_total, discount_amount, delivery_charge = calculate_order_total(subtotal, division, applied_coupon)
    
    order_data = {
        'product_id': product.id, 'product_name': product.name, 'product_price': product.final_price, 'product_image': product.images[0].image_url if product.images else '',
        'size': request.form.get('size'), 'quantity': qty, 'name': request.form.get('name'), 'phone': request.form.get('phone'),
        'full_address': f"{request.form.get('address')}, {district}, {division}", 'payment_method': request.form.get('payment_method'), 'trx_id': request.form.get('trx_id')
    }
    
    if 'payment_screenshot' in request.files:
        file = request.files['payment_screenshot']
        if file:
            fname = secure_filename(f"pay_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['PAYMENT_UPLOAD_FOLDER'], fname))
            order_data['payment_screenshot'] = fname

    new_order = Order(
        user_id=current_user.id if current_user.is_authenticated else None, customer_name=order_data['name'], phone=order_data['phone'], 
        address=order_data['full_address'], delivery_charge=delivery_charge, discount_amount=discount_amount, total_price=final_total, 
        applied_coupon=applied_coupon, payment_method=order_data['payment_method'], trx_id=order_data.get('trx_id'), payment_screenshot=order_data.get('payment_screenshot')
    )
    db.session.add(new_order); db.session.flush()
    db.session.add(OrderItem(order_id=new_order.id, product_id=product.id, product_name=product.name, product_price=product.final_price, product_size=order_data['size'], product_image=order_data['product_image'], quantity=order_data['quantity']))
    db.session.commit()
    
    return redirect(url_for('order_success', order_id=new_order.id))

@app.route('/order-success/<int:order_id>')
def order_success(order_id): 
    order = Order.query.get_or_404(order_id)
    if current_user.is_authenticated and order.user_id != current_user.id and not current_user.is_admin: return redirect(url_for('home'))
    return render_template('order_success.html', order=order)

@app.route('/track-order', methods=['GET', 'POST'])
def track_order_route(): 
    if request.method == 'POST':
        order_id = request.form.get('order_id')
        phone = request.form.get('phone')
        order = Order.query.filter_by(id=order_id, phone=phone).first()
        if order:
            return render_template('track_order.html', order=order)
        flash('Invalid Order ID or Phone Number!', 'error')
        return redirect(url_for('track_order_route'))
    
    oid = request.args.get('id')
    if oid and current_user.is_authenticated:
        order = Order.query.get(oid)
        if order and (order.user_id == current_user.id or current_user.is_admin):
            return render_template('track_order.html', order=order)
            
    return render_template('track_search.html')

@app.route('/my-orders')
@login_required
def my_orders_route():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.date_ordered.desc()).all()
    stats = {'total': len(orders), 'delivered': len([o for o in orders if o.status == 'Delivered']), 'cancelled': len([o for o in orders if o.status == 'Cancelled']), 'success_rate': int((len([o for o in orders if o.status == 'Delivered']) / len(orders)) * 100) if len(orders) > 0 else 0}
    return render_template('my_orders.html', orders=orders, stats=stats)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_route():
    if request.method == 'POST':
        current_user.name = request.form.get('name'); current_user.phone = request.form.get('phone'); current_user.address = request.form.get('address')
        if not current_user.dob and request.form.get('dob'): current_user.dob = request.form.get('dob')
        db.session.commit(); flash('Profile Updated Successfully!', 'success')
        return redirect(url_for('profile_route'))
    return render_template('profile.html', user=current_user)

@app.route('/invoice/<int:order_id>')
@login_required
def generate_invoice_route(order_id): 
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id and not current_user.is_admin: return redirect(url_for('my_orders_route'))
    return render_template('invoice.html', order=order)

@app.route('/submit-review', methods=['POST'])
def submit_review_route():
    prod_id = request.form.get('product_id'); rating = int(request.form.get('rating', 5)); comment = request.form.get('comment', '')
    name = current_user.name if current_user.is_authenticated else request.form.get('guest_name', 'Guest User')
    uid = current_user.id if current_user.is_authenticated else None
    
    image_filename = None
    if 'review_image' in request.files:
        file = request.files['review_image']
        if file:
            image_filename = secure_filename(f"rev_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['REVIEW_UPLOAD_FOLDER'], image_filename))

    db.session.add(Review(user_id=uid, customer_name=name, product_id=prod_id, rating=rating, comment=comment, image_url=image_filename))
    db.session.commit()
    return jsonify({'status': 'success'})

# ==========================================
# 👑 ADMIN PANEL
# ==========================================
@app.route('/secret-admin-setup/<secret_key>')
def secret_admin_setup(secret_key):
    if secret_key == 'make_me_admin_2026':
        if current_user.is_authenticated:
            current_user.is_admin = True; db.session.commit(); return "Success! Go to /admin"
        return "Please login first."
    return "Invalid Key"

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin: return redirect(url_for('home'))
    return render_template('admin_dashboard.html', products=Product.query.order_by(Product.id.desc()).all())

@app.route('/admin/add-product-page')
@login_required
def admin_add_product_page():
    if not current_user.is_admin: return redirect(url_for('home'))
    return render_template('admin_add_product.html')

@app.route('/admin/add-product', methods=['POST'])
@login_required
def add_product():
    if not current_user.is_admin: return redirect(url_for('home'))
    size_data = {'M': {'chest': request.form.get('m_chest'), 'length': request.form.get('m_len'), 'sleeve': request.form.get('m_sleeve'), 'waist': request.form.get('m_waist')},'L': {'chest': request.form.get('l_chest'), 'length': request.form.get('l_len'), 'sleeve': request.form.get('l_sleeve'), 'waist': request.form.get('l_waist')},'XL': {'chest': request.form.get('xl_chest'), 'length': request.form.get('xl_len'), 'sleeve': request.form.get('xl_sleeve'), 'waist': request.form.get('xl_waist')},'XXL': {'chest': request.form.get('xxl_chest'), 'length': request.form.get('xxl_len'), 'sleeve': request.form.get('xxl_sleeve'), 'waist': request.form.get('xxl_waist')}}
    p = Product(name=request.form['name'], price=float(request.form['price']), discount=int(request.form.get('discount', 0)), stock=int(request.form['stock']), category=request.form['category'].strip().title(), gender=request.form.get('gender', 'Men'), description=request.form['description'], sizes=request.form.get('sizes'), size_chart=json.dumps(size_data), is_luxury=(request.form.get('is_luxury') == 'on'))
    db.session.add(p); db.session.commit()
    for file in request.files.getlist('images'):
        if file: 
            fname = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"); file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname)); db.session.add(ProductImage(image_url=fname, product_id=p.id))
    db.session.commit(); return redirect(url_for('admin_dashboard'))

@app.route('/admin/edit-product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_admin: return redirect(url_for('home'))
    p = Product.query.get_or_404(product_id)
    if request.method == 'POST':
        p.name = request.form['name']; p.price = float(request.form['price']); p.discount = int(request.form.get('discount', 0)); p.stock = int(request.form['stock']); p.category = request.form['category'].strip().title(); p.gender = request.form.get('gender', 'Men'); p.description = request.form['description']; p.sizes = request.form.get('sizes'); p.is_luxury = (request.form.get('is_luxury') == 'on') 
        size_data = {'M': {'chest': request.form.get('m_chest'), 'length': request.form.get('m_len'), 'sleeve': request.form.get('m_sleeve'), 'waist': request.form.get('m_waist')},'L': {'chest': request.form.get('l_chest'), 'length': request.form.get('l_len'), 'sleeve': request.form.get('l_sleeve'), 'waist': request.form.get('l_waist')},'XL': {'chest': request.form.get('xl_chest'), 'length': request.form.get('xl_len'), 'sleeve': request.form.get('xl_sleeve'), 'waist': request.form.get('xl_waist')},'XXL': {'chest': request.form.get('xxl_chest'), 'length': request.form.get('xxl_len'), 'sleeve': request.form.get('xxl_sleeve'), 'waist': request.form.get('xxl_waist')}}
        p.size_chart = json.dumps(size_data); files = request.files.getlist('images')
        if files and files[0].filename:
            ProductImage.query.filter_by(product_id=p.id).delete()
            for file in files:
                fname = secure_filename(f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"); file.save(os.path.join(app.config['UPLOAD_FOLDER'], fname)); db.session.add(ProductImage(image_url=fname, product_id=p.id))
        db.session.commit(); return redirect(url_for('admin_dashboard'))
    return render_template('admin_edit_product.html', product=p)

@app.route('/admin/delete-product/<int:id>', methods=['POST'])
@login_required
def delete_product(id): 
    if not current_user.is_admin: return redirect(url_for('home'))
    Product.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin_dashboard'))

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin: return redirect(url_for('home'))
    
    today = datetime.now().date()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    all_orders = Order.query.all()
    stats = {
        'today': {'total': 0, 'pending': 0, 'delivered': 0, 'cancelled': 0, 'revenue': 0},
        'week': {'total': 0, 'pending': 0, 'delivered': 0, 'cancelled': 0, 'revenue': 0},
        'month': {'total': 0, 'pending': 0, 'delivered': 0, 'cancelled': 0, 'revenue': 0},
        'all_time': {'total': 0, 'pending': 0, 'delivered': 0, 'cancelled': 0, 'revenue': 0}
    }
    
    for o in all_orders:
        o_date = o.date_ordered.date()
        def update_stat(time_key):
            stats[time_key]['total'] += 1
            if o.status == 'Pending': stats[time_key]['pending'] += 1
            elif o.status == 'Delivered': stats[time_key]['delivered'] += 1; stats[time_key]['revenue'] += int(o.total_price)
            elif o.status == 'Cancelled': stats[time_key]['cancelled'] += 1
            
        update_stat('all_time')
        if o_date == today: update_stat('today')
        if o_date >= start_of_week: update_stat('week')
        if o_date >= start_of_month: update_stat('month')
    
    # 🔥 SEARCH & FILTER LOGIC FIX 🔥
    query = Order.query
    
    status_filter = request.args.get('status', 'All')
    filter_date = request.args.get('filter_date')
    search_query = request.args.get('search_query')
    
    if status_filter != 'All': 
        query = query.filter(Order.status == status_filter)
        
    if filter_date:
        try:
            date_obj = datetime.strptime(filter_date, '%Y-%m-%d').date()
            start_of_day = datetime.combine(date_obj, datetime.min.time())
            end_of_day = start_of_day + timedelta(days=1)
            query = query.filter(Order.date_ordered >= start_of_day, Order.date_ordered < end_of_day)
        except ValueError: 
            pass
            
    if search_query: 
        query = query.filter(or_(Order.customer_name.ilike(f'%{search_query}%'), Order.phone.ilike(f'%{search_query}%')))
    
    orders = query.order_by(Order.date_ordered.desc()).all()
    
    counts = {
        'All': Order.query.count(), 
        'Pending': Order.query.filter_by(status='Pending').count(), 
        'Confirmed': Order.query.filter_by(status='Confirmed').count(), 
        'Shipped': Order.query.filter_by(status='Shipped').count(), 
        'Delivered': Order.query.filter_by(status='Delivered').count(), 
        'Cancelled': Order.query.filter_by(status='Cancelled').count()
    }
    
    return render_template('admin_orders.html', orders=orders, counts=counts, stats=stats, current_status=status_filter, search_query=search_query, current_filter=filter_date)

@app.route('/admin/update-order/<int:id>', methods=['POST'])
@login_required
def update_order_status(id): 
    if not current_user.is_admin: return redirect(url_for('home'))
    o = Order.query.get(id); o.status = request.form['status']; db.session.commit()
    return redirect(request.referrer or url_for('admin_orders'))

@app.route('/admin/banners')
@login_required
def admin_banners(): 
    if not current_user.is_admin: return redirect(url_for('home'))
    return render_template('admin_banners.html', banners=Banner.query.all())

@app.route('/admin/add-banner', methods=['POST'])
@login_required
def add_banner():
    if not current_user.is_admin: return redirect(url_for('home'))
    if 'banner_image' in request.files:
        f = request.files['banner_image']
        if f: 
            fname = secure_filename(f"banner_{datetime.now().strftime('%Y%m%d%H%M%S')}_{f.filename}"); f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname)); db.session.add(Banner(image_url=fname)); db.session.commit()
    return redirect(url_for('admin_banners'))

@app.route('/admin/delete-banner/<int:id>', methods=['POST'])
@login_required
def delete_banner(id): 
    if not current_user.is_admin: return redirect(url_for('home'))
    Banner.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin_banners'))

@app.route('/admin/campaigns')
@login_required
def admin_campaigns(): 
    if not current_user.is_admin: return redirect(url_for('home'))
    return render_template('admin_campaigns.html', coupons=Coupon.query.all())

@app.route('/admin/add-coupon', methods=['POST'])
@login_required
def add_coupon(): 
    if not current_user.is_admin: return redirect(url_for('home'))
    db.session.add(Coupon(code=request.form['code'].upper(), discount_percent=int(request.form['discount']), min_spend=float(request.form['min_spend']))); db.session.commit()
    return redirect(url_for('admin_campaigns'))

@app.route('/admin/delete-coupon/<int:id>', methods=['POST'])
@login_required
def delete_coupon(id): 
    if not current_user.is_admin: return redirect(url_for('home'))
    Coupon.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin_campaigns'))

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin: return redirect(url_for('home'))
    return render_template('admin_users.html', users=User.query.filter_by(is_admin=False).order_by(User.id.desc()).all())

@app.route('/admin/delete-user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    if not current_user.is_admin: return redirect(url_for('home'))
    u = User.query.get_or_404(id); CartItem.query.filter_by(user_id=u.id).delete(); Review.query.filter_by(user_id=u.id).delete(); db.session.delete(u); db.session.commit(); return redirect(url_for('admin_users'))

@app.route('/admin/toggle-ban/<int:id>', methods=['POST'])
@login_required
def toggle_ban(id):
    if not current_user.is_admin: return redirect(url_for('home'))
    u = User.query.get_or_404(id); u.is_banned = not getattr(u, 'is_banned', False); db.session.commit(); return redirect(url_for('admin_users'))

@app.route('/admin/feedback')
@login_required
def admin_feedback():
    if not current_user.is_admin: return redirect(url_for('home'))
    return render_template('admin_feedback.html', feedbacks=Feedback.query.order_by(Feedback.created_at.desc()).all())

@app.route('/admin/delete-feedback/<int:id>', methods=['POST'])
@login_required
def delete_feedback(id):
    if not current_user.is_admin: return redirect(url_for('home'))
    Feedback.query.filter_by(id=id).delete(); db.session.commit(); return redirect(url_for('admin_feedback'))

@app.route('/api/ai-stylist', methods=['POST'])
def api_ai_stylist():
    data = request.json or {}; user_message = data.get('message', '').strip()
    if not user_message: return jsonify({'status': 'error', 'reply': 'Empty message.'})
    try:
        product_context = "\n".join([f"- {p.name}, {p.category}, {p.gender}, ৳{p.final_price}" for p in Product.query.all()])
        sys_inst = f"You are AIVARO AI Stylist. Be polite, elegant. Recommend these products if relevant:\n{product_context}"
        client = genai.Client(api_key=app.config['GEMINI_API_KEY'])
        response = client.models.generate_content(model='gemini-1.5-flash', contents=user_message, config=genai.types.GenerateContentConfig(system_instruction=sys_inst,))
        return jsonify({'status': 'success', 'reply': response.text})
    except Exception as e:
        return jsonify({'status': 'error', 'reply': "Servers are busy. Please try again."})

# 🔥 Auto Create DB
if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)