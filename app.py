import os
import re
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user, logout_user,
                         login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pc-shop-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Войдите в аккаунт, чтобы открыть эту страницу.'
login_manager.login_message_category = 'error'

MAX_QUANTITY = 10

CATEGORY_ORDER = [
    'Процессор',
    'Материнская плата',
    'Видеокарта',
    'Оперативная память',
    'Накопитель',
    'Блок питания',
    'Корпус',
    'Охлаждение',
]

SOCKETS = {
    'Intel Core i3-12100F': 'LGA1700',
    'AMD Ryzen 5 7600': 'AM5',
    'AMD Ryzen 7 7800X3D': 'AM5',
    'MSI PRO B760M-A': 'LGA1700',
    'ASUS TUF GAMING B650-PLUS': 'AM5',
    'ASUS ROG STRIX X670E-E': 'AM5',
}

GPU_MIN_PSU = {
    'GeForce RTX 5060 8 ГБ': 550,
    'GeForce RTX 5070 12 ГБ': 650,
    'GeForce RTX 5080 16 ГБ': 850,
}

PSU_POWER = {
    '550 Вт 80+ Bronze': 550,
    '750 Вт 80+ Gold': 750,
    '1000 Вт 80+ Gold': 1000,
}


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


computer_components = db.Table(
    'computer_components',
    db.Column('computer_id', db.Integer, db.ForeignKey('computer.id'), primary_key=True),
    db.Column('component_id', db.Integer, db.ForeignKey('component.id'), primary_key=True),
)


class Component(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Integer, nullable=False)


class Computer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image = db.Column(db.String(100))
    is_custom = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    components = db.relationship('Component', secondary=computer_components)

    @property
    def price(self) -> int:
        return sum(component.price for component in self.components)

    @property
    def sorted_components(self) -> list:
        return sorted(self.components, key=lambda c: CATEGORY_ORDER.index(c.category))

    @property
    def image_file(self) -> str:
        if self.image:
            return self.image
        return 'custom.jpg' if self.is_custom else ''

    @property
    def image_exists(self) -> bool:
        if not self.image_file:
            return False
        return os.path.exists(os.path.join(app.static_folder, 'img', self.image_file))


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    computer_id = db.Column(db.Integer, db.ForeignKey('computer.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    computer = db.relationship(
        'Computer',
        backref=db.backref('cart_items', cascade='all, delete-orphan'),
    )

    __table_args__ = (db.UniqueConstraint('user_id', 'computer_id'),)

    @property
    def total(self) -> int:
        return self.computer.price * self.quantity


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    status = db.Column(db.String(30), nullable=False, default='Принят')
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    address = db.Column(db.String(300), nullable=False)
    comment = db.Column(db.String(300))
    total = db.Column(db.Integer, nullable=False)

    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    components = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)
    quantity = db.Column(db.Integer, nullable=False)

    @property
    def total(self) -> int:
        return self.price * self.quantity


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


@app.template_filter('price')
def format_price(value: int) -> str:
    return f'{value:,}'.replace(',', ' ') + ' ₽'


@app.template_filter('date')
def format_date(value: datetime) -> str:
    return value.strftime('%d.%m.%Y %H:%M')


@app.context_processor
def inject_cart_count() -> dict:
    count = 0
    if current_user.is_authenticated:
        count = (db.session.query(db.func.sum(CartItem.quantity))
                 .filter_by(user_id=current_user.id).scalar()) or 0
    return {'cart_count': count}


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


def check_compatibility(parts: dict):
    cpu = parts['Процессор']
    board = parts['Материнская плата']
    if SOCKETS.get(cpu.name) != SOCKETS.get(board.name):
        return (f'Процессор {cpu.name} не подходит к плате {board.name}: '
                f'у них разные сокеты.')

    gpu = parts['Видеокарта']
    psu = parts['Блок питания']
    need = GPU_MIN_PSU.get(gpu.name, 0)
    if PSU_POWER.get(psu.name, 0) < need:
        return f'Для видеокарты {gpu.name} нужен блок питания от {need} Вт.'

    return None


def can_view(computer: Computer) -> bool:
    if not computer.is_custom:
        return True
    return current_user.is_authenticated and computer.user_id == current_user.id


def get_own_cart_item(item_id: int) -> CartItem:
    item = db.get_or_404(CartItem, item_id)
    if item.user_id != current_user.id:
        abort(404)
    return item


@app.route('/')
def index() -> str:
    computers = Computer.query.filter_by(is_custom=False).all()
    return render_template('index.html', computers=computers)


@app.route('/computer/<int:computer_id>')
def computer_detail(computer_id: int) -> str:
    computer = db.get_or_404(Computer, computer_id)
    if not can_view(computer):
        abort(404)
    return render_template('computer.html', computer=computer)


@app.route('/configurator', methods=['GET', 'POST'])
def configurator():
    groups = [
        (category, Component.query.filter_by(category=category)
                                  .order_by(Component.price).all())
        for category in CATEGORY_ORDER
    ]
    selected = {category: items[0].id for category, items in groups if items}
    build_name = 'Моя сборка'

    if request.method == 'POST':
        if not current_user.is_authenticated:
            flash('Войдите, чтобы сохранить сборку.', 'error')
            return redirect(url_for('login', next=url_for('configurator')))

        build_name = request.form.get('name', '').strip()
        parts = {}
        error = None

        for category in CATEGORY_ORDER:
            component_id = request.form.get(category, type=int)
            component = db.session.get(Component, component_id) if component_id else None
            if component is None or component.category != category:
                error = f'Не выбрано: {category.lower()}.'
                break
            parts[category] = component
            selected[category] = component.id

        if error is None:
            if not build_name:
                error = 'Введите название сборки.'
            elif len(build_name) > 100:
                error = 'Название слишком длинное (до 100 символов).'
            else:
                error = check_compatibility(parts)

        if error:
            flash(error, 'error')
        else:
            computer = Computer(name=build_name, is_custom=True, user_id=current_user.id)
            computer.components = list(parts.values())
            db.session.add(computer)
            db.session.commit()

            flash(f'Сборка «{build_name}» сохранена!', 'success')
            return redirect(url_for('computer_detail', computer_id=computer.id))

    return render_template('configurator.html', groups=groups,
                           selected=selected, build_name=build_name)


@app.route('/computer/<int:computer_id>/delete', methods=['POST'])
@login_required
def delete_computer(computer_id: int):
    computer = db.get_or_404(Computer, computer_id)

    if not computer.is_custom or computer.user_id != current_user.id:
        abort(404)

    db.session.delete(computer)
    db.session.commit()

    flash(f'Сборка «{computer.name}» удалена.', 'success')
    return redirect(url_for('profile'))


@app.route('/cart')
@login_required
def cart() -> str:
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.total for item in items)
    return render_template('cart.html', items=items, total=total)


@app.route('/cart/add/<int:computer_id>', methods=['POST'])
@login_required
def add_to_cart(computer_id: int):
    computer = db.get_or_404(Computer, computer_id)
    if not can_view(computer):
        abort(404)

    item = CartItem.query.filter_by(user_id=current_user.id,
                                    computer_id=computer.id).first()
    if item:
        if item.quantity >= MAX_QUANTITY:
            flash(f'Можно добавить не больше {MAX_QUANTITY} шт. одного компьютера.', 'error')
            return redirect(url_for('cart'))
        item.quantity += 1
    else:
        db.session.add(CartItem(user_id=current_user.id, computer_id=computer.id))

    db.session.commit()
    flash(f'«{computer.name}» добавлен в корзину.', 'success')
    return redirect(url_for('cart'))


@app.route('/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id: int):
    item = get_own_cart_item(item_id)
    action = request.form.get('action')

    if action == 'plus':
        if item.quantity < MAX_QUANTITY:
            item.quantity += 1
        else:
            flash(f'Можно добавить не больше {MAX_QUANTITY} шт. одного компьютера.', 'error')
    elif action == 'minus':
        item.quantity -= 1
        if item.quantity <= 0:
            db.session.delete(item)

    db.session.commit()
    return redirect(url_for('cart'))


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id: int):
    item = get_own_cart_item(item_id)
    name = item.computer.name
    db.session.delete(item)
    db.session.commit()

    flash(f'«{name}» удалён из корзины.', 'success')
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not items:
        flash('Корзина пуста — нечего оформлять.', 'error')
        return redirect(url_for('cart'))

    total = sum(item.total for item in items)
    form = {'full_name': current_user.username, 'phone': '', 'address': '', 'comment': ''}

    if request.method == 'POST':
        form = {key: request.form.get(key, '').strip() for key in form}
        phone_digits = re.sub(r'\D', '', form['phone'])

        error = None
        if not form['full_name'] or not form['phone'] or not form['address']:
            error = 'Заполните имя, телефон и адрес.'
        elif len(form['full_name']) > 100:
            error = 'Имя слишком длинное (до 100 символов).'
        elif len(phone_digits) not in (10, 11):
            error = 'Введите корректный номер телефона.'
        elif len(form['address']) > 300 or len(form['comment']) > 300:
            error = 'Адрес и комментарий — не длиннее 300 символов.'

        if error:
            flash(error, 'error')
        else:
            order = Order(
                user_id=current_user.id,
                full_name=form['full_name'],
                phone=form['phone'],
                address=form['address'],
                comment=form['comment'] or None,
                total=total,
            )
            for item in items:
                order.items.append(OrderItem(
                    name=item.computer.name,
                    components=', '.join(part.name for part in item.computer.sorted_components),
                    price=item.computer.price,
                    quantity=item.quantity,
                ))
                db.session.delete(item)

            db.session.add(order)
            db.session.commit()

            flash(f'Заказ №{order.id} оформлен! Спасибо за покупку.', 'success')
            return redirect(url_for('order_detail', order_id=order.id))

    return render_template('checkout.html', items=items, total=total, form=form)


@app.route('/orders')
@login_required
def orders() -> str:
    user_orders = (Order.query.filter_by(user_id=current_user.id)
                   .order_by(Order.created_at.desc()).all())
    return render_template('orders.html', orders=user_orders)


@app.route('/orders/<int:order_id>')
@login_required
def order_detail(order_id: int) -> str:
    order = db.get_or_404(Order, order_id)
    if order.user_id != current_user.id:
        abort(404)
    return render_template('order.html', order=order)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        password2 = request.form['password2']

        error = None
        if not username or not email or not password:
            error = 'Заполните все поля.'
        elif len(password) < 6:
            error = 'Пароль должен быть не короче 6 символов.'
        elif password != password2:
            error = 'Пароли не совпадают.'
        elif User.query.filter_by(username=username).first():
            error = 'Пользователь с таким логином уже существует.'
        elif User.query.filter_by(email=email).first():
            error = 'Этот email уже зарегистрирован.'

        if error:
            flash(error, 'error')
            return render_template('register.html', username=username, email=email)

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь войдите в аккаунт.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        login_value = request.form['login'].strip()
        password = request.form['password']
        remember = 'remember' in request.form

        user = User.query.filter(
            (User.username == login_value) | (User.email == login_value.lower())
        ).first()

        if user is None or not check_password_hash(user.password_hash, password):
            flash('Неверный логин или пароль.', 'error')
            return render_template('login.html', login_value=login_value)

        login_user(user, remember=remember)
        flash(f'С возвращением, {user.username}!', 'success')

        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/') or next_page.startswith('//'):
            next_page = url_for('index')
        return redirect(next_page)

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта.', 'success')
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile() -> str:
    builds = Computer.query.filter_by(user_id=current_user.id, is_custom=True).all()
    return render_template('profile.html', builds=builds)


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)