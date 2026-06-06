from flask import Flask, render_template, request, redirect, url_for, flash
from database import init_db, get_db
import os

app = Flask(__name__)
app.secret_key = 'cooldrinks-secret-key-2024'

# ── Init ──────────────────────────────────────────────────────────────────────
with app.app_context():
    init_db()


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/')
def dashboard():
    db = get_db()
    total_products   = db.execute('SELECT COUNT(*) FROM products').fetchone()[0]
    total_stock      = db.execute('SELECT COALESCE(SUM(stock), 0) FROM products').fetchone()[0]
    total_inv_value  = db.execute('SELECT COALESCE(SUM(price * stock), 0) FROM products').fetchone()[0]
    total_bills      = db.execute('SELECT COUNT(*) FROM bills').fetchone()[0]
    total_revenue    = db.execute('SELECT COALESCE(SUM(total), 0) FROM bills').fetchone()[0]
    low_stock        = db.execute(
        'SELECT name, stock FROM products WHERE stock <= 20 ORDER BY stock ASC LIMIT 5'
    ).fetchall()
    recent_bills     = db.execute(
        '''SELECT b.id, b.created_at, b.total, p.name as product_name, bi.quantity
           FROM bills b
           JOIN bill_items bi ON bi.bill_id = b.id
           JOIN products p    ON p.id = bi.product_id
           ORDER BY b.created_at DESC LIMIT 5'''
    ).fetchall()
    db.close()
    return render_template('dashboard.html',
        total_products=total_products,
        total_stock=total_stock,
        total_inv_value=total_inv_value,
        total_bills=total_bills,
        total_revenue=total_revenue,
        low_stock=low_stock,
        recent_bills=recent_bills,
    )


# ── Products ──────────────────────────────────────────────────────────────────
@app.route('/products')
def products():
    db = get_db()
    all_products = db.execute('SELECT * FROM products ORDER BY name').fetchall()
    db.close()
    return render_template('products.html', products=all_products)


@app.route('/products/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name  = request.form['name'].strip()
        price = request.form['price'].strip()
        stock = request.form['stock'].strip()

        if not name or not price or not stock:
            flash('All fields are required.', 'error')
            return render_template('add_product.html')

        try:
            price = float(price)
            stock = int(stock)
            if price <= 0 or stock < 0:
                raise ValueError
        except ValueError:
            flash('Price must be a positive number and stock a non-negative integer.', 'error')
            return render_template('add_product.html')

        db = get_db()
        try:
            db.execute('INSERT INTO products (name, price, stock) VALUES (?, ?, ?)',
                       (name, price, stock))
            db.commit()
            flash(f'Product "{name}" added successfully!', 'success')
        except Exception:
            flash(f'A product named "{name}" already exists.', 'error')
        finally:
            db.close()
        return redirect(url_for('products'))

    return render_template('add_product.html')


@app.route('/products/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    db = get_db()
    product = db.execute('SELECT name FROM products WHERE id = ?', (product_id,)).fetchone()
    if product:
        db.execute('DELETE FROM products WHERE id = ?', (product_id,))
        db.commit()
        flash(f'Product "{product["name"]}" deleted.', 'success')
    else:
        flash('Product not found.', 'error')
    db.close()
    return redirect(url_for('products'))


# ── Stock Management ───────────────────────────────────────────────────────────
@app.route('/products/add-stock/<int:product_id>', methods=['GET', 'POST'])
def add_stock(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        flash('Product not found.', 'error')
        db.close()
        return redirect(url_for('products'))

    if request.method == 'POST':
        qty = request.form['quantity'].strip()
        try:
            qty = int(qty)
            if qty <= 0:
                raise ValueError
        except ValueError:
            flash('Quantity must be a positive integer.', 'error')
            db.close()
            return render_template('add_stock.html', product=product)

        new_stock = product['stock'] + qty
        db.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
        db.commit()
        flash(f'Added {qty} cartons. New stock: {new_stock}.', 'success')
        db.close()
        return redirect(url_for('products'))

    db.close()
    return render_template('add_stock.html', product=product)


@app.route('/products/remove-stock/<int:product_id>', methods=['GET', 'POST'])
def remove_stock(product_id):
    db = get_db()
    product = db.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    if not product:
        flash('Product not found.', 'error')
        db.close()
        return redirect(url_for('products'))

    if request.method == 'POST':
        qty = request.form['quantity'].strip()
        try:
            qty = int(qty)
            if qty <= 0:
                raise ValueError
        except ValueError:
            flash('Quantity must be a positive integer.', 'error')
            db.close()
            return render_template('remove_stock.html', product=product)

        if product['stock'] - qty < 0:
            flash(f'Cannot remove {qty} cartons — only {product["stock"]} in stock.', 'error')
            db.close()
            return render_template('remove_stock.html', product=product)

        new_stock = product['stock'] - qty
        db.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
        db.commit()
        flash(f'Removed {qty} cartons. New stock: {new_stock}.', 'success')
        db.close()
        return redirect(url_for('products'))

    db.close()
    return render_template('remove_stock.html', product=product)


# ── Billing ───────────────────────────────────────────────────────────────────
@app.route('/billing', methods=['GET', 'POST'])
def generate_bill():
    db = get_db()

    products_list = db.execute(
        'SELECT * FROM products WHERE stock > 0 ORDER BY name'
    ).fetchall()

    if request.method == 'POST':

        customer_name = request.form.get('customer_name', '').strip()
        customer_mobile = request.form.get('customer_mobile', '').strip()

        selected_products = []
        total_amount = 0

        for product in products_list:

            qty = int(request.form.get(f'qty_{product["id"]}', 0))

            if qty > 0:

                if qty > product['stock']:
                    flash(
                        f'Only {product["stock"]} cartons available for {product["name"]}',
                        'error'
                    )
                    db.close()
                    return render_template(
                        'generate_bill.html',
                        products=products_list
                    )

                subtotal = product['price'] * qty

                selected_products.append({
                    'product': product,
                    'quantity': qty,
                    'subtotal': subtotal
                })

                total_amount += subtotal

        if not selected_products:
            flash('Please select at least one product.', 'error')
            db.close()
            return render_template(
                'generate_bill.html',
                products=products_list
            )

        cursor = db.execute(
            '''
            INSERT INTO bills
            (customer_name, customer_mobile, total)
            VALUES (?, ?, ?)
            ''',
            (
                customer_name,
                customer_mobile,
                total_amount
            )
        )

        bill_id = cursor.lastrowid

        for item in selected_products:

            db.execute(
                '''
                INSERT INTO bill_items
                (bill_id, product_id, quantity, subtotal)
                VALUES (?, ?, ?, ?)
                ''',
                (
                    bill_id,
                    item['product']['id'],
                    item['quantity'],
                    item['subtotal']
                )
            )

            db.execute(
                '''
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
                ''',
                (
                    item['quantity'],
                    item['product']['id']
                )
            )

        db.commit()

        flash(
            f'Bill #{bill_id} generated successfully!',
            'success'
        )

        db.close()

        return redirect(url_for('bill_history'))

    db.close()

    return render_template(
        'generate_bill.html',
        products=products_list
    )
@app.route('/bill/<int:bill_id>')
def view_bill(bill_id):
    db = get_db()

    bill = db.execute(
        '''
        SELECT *
        FROM bills
        WHERE id = ?
        ''',
        (bill_id,)
    ).fetchone()

    items = db.execute(
        '''
        SELECT
            p.name,
            bi.quantity,
            bi.subtotal
        FROM bill_items bi
        JOIN products p
            ON p.id = bi.product_id
        WHERE bi.bill_id = ?
        ''',
        (bill_id,)
    ).fetchall()

    db.close()

    return render_template(
        'view_bill.html',
        bill=bill,
        items=items
    )
@app.route('/bills')
def bill_history():
    db = get_db()

    bills = db.execute(
        '''
        SELECT
            b.id,
            b.created_at,
            b.total,
            COUNT(bi.id) AS item_count
        FROM bills b
        LEFT JOIN bill_items bi
            ON bi.bill_id = b.id
        GROUP BY b.id
        ORDER BY b.created_at DESC
        '''
    ).fetchall()

    db.close()

    return render_template(
        'bill_history.html',
        bills=bills
    )
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)