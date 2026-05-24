from db import Database
from login_ui import Ui_Login
from main_window_ui import Ui_MainWindow
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6 import QtGui
from qt_material import apply_stylesheet

def db():
    return Database()

class BaseWindow(QMainWindow):
    def go_back(self):
        self.back = LoginWindow()
        self.back.show()
        self.close()

    def clear_cards(self):
        while self.ui.verticalLayout_card.count():
            item = self.ui.verticalLayout_card.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def fill_table(self, table, rows):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row.values()):
                table.setItem(r, c, QTableWidgetItem(str(val)))

    def load_categories(self, all_label="Все товары"):
        self.ui.comboBox_sorting.addItem(all_label, 0)
        d = db()
        d.cursor.execute('SELECT * FROM categories')
        for cat in d.cursor.fetchall():
            self.ui.comboBox_sorting.addItem(cat['name'], cat['category_id'])

    def load_data(self):
        self.clear_cards()
        cid = self.ui.comboBox_sorting.currentData()
        cur = db().cursor
        if cid == 0:
            cur.execute('SELECT * FROM products')
        else:
            cur.execute('SELECT * FROM products WHERE category_id = %s', (cid,))
        for product in cur.fetchall():
            self.add_card(product)

    def add_card(self, product):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(frame)

        photo = QLabel()
        photo.setFixedSize(80, 80)
        photo.setPixmap(QPixmap(product['image_path'] or "images/zagl.png").scaled(80, 80))
        layout.addWidget(photo)

        layout.addWidget(QLabel(
            f"{product['name']} | {product['sku']}\n"
            f"Описание: {product['description']}\n"
            f"Цена: {product['price']} руб."
        ))

        disc = QLabel(f"Скидка: \n {product['discount']}%")
        disc.setFixedSize(80, 80)
        layout.addWidget(disc)

        self.add_card_extra(layout, product)
        self.ui.verticalLayout_card.addWidget(frame)

    def add_card_extra(self, layout, product):
        pass


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Login()
        self.ui.setupUi(self)
        self.setWindowTitle('Магазин "Kvalik Shop"')
        self.ui.pushButton_guest.clicked.connect(self.go_guest)
        self.ui.pushButton_login.clicked.connect(self.handle_login)

    def handle_login(self):
        login = self.ui.lineEdit_login.text()
        password = self.ui.lineEdit_password.text()
        cur = db().cursor
        cur.execute('SELECT * FROM users WHERE username = %s AND password_hash = %s', (login, password))
        user = cur.fetchone()
        if user:
            if user['role'] == 'client':
                self.main = ClientWindow(user)
            elif user['role'] in ('manager', 'admin'):
                self.main = ManagerWindow(user)
            else:
                QMessageBox.warning(self, "Ошибка", "Недостаточно прав")
                return
            self.main.show()
            self.close()
        else:
            QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль")

    def go_guest(self):
        self.guest = GuestWindow()
        self.guest.show()
        self.close()


class ManagerWindow(BaseWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Окно для Менеджера")
        self.ui.label_user.setText(f"Пользователь: {user['full_name']} ({user['role']})")

        self.ui.tabWidget.removeTab(2)
        self.ui.groupOrder_2.hide()
        self.ui.groupSelection_2.hide()
        self.ui.pushButton_cancelOrder.hide()

        self.load_categories("Все товары")
        self.ui.comboBox_sorting.currentIndexChanged.connect(self.load_data)
        self.load_data()

        self.load_status()
        self.ui.comboBox_sorting_stat.currentIndexChanged.connect(self.load_orders)
        self.load_orders()

        self.ui.comboBox_new_stat.addItems(["новый", "обработка", "отправлено", "доставлено", "отменено", "возврат"])
        self.ui.pushButton_editStatus.clicked.connect(self.update_order_status)
        self.ui.pushButton_logout.clicked.connect(self.go_back)

    def load_status(self):
        d = db()
        d.cursor.execute('SELECT DISTINCT status FROM orders')
        self.ui.comboBox_sorting_stat.addItem("Все", "")
        for s in d.cursor.fetchall():
            self.ui.comboBox_sorting_stat.addItem(s['status'], s['status'])

    def load_orders(self):
        status = self.ui.comboBox_sorting_stat.currentData()
        d = db()
        query = """SELECT o.order_id, u.username, p.name, pv.size, pv.color,
                          oi.quantity, o.total_amount, o.status, o.order_date
                   FROM orders o
                   JOIN users u ON o.user_id = u.user_id
                   JOIN order_items oi ON o.order_id = oi.order_id
                   JOIN product_variants pv ON oi.variant_id = pv.variant_id
                   JOIN products p ON pv.product_id = p.product_id"""
        if status == "":
            d.cursor.execute(query)
        else:
            d.cursor.execute(query + " WHERE o.status = %s", (status,))
        self.fill_table(self.ui.tableWidget_orders, d.cursor.fetchall())

    def update_order_status(self):
        row = self.ui.tableWidget_orders.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        order_id = self.ui.tableWidget_orders.item(row, 0).text()
        new_status = self.ui.comboBox_new_stat.currentText()
        d = db()
        d.cursor.execute("UPDATE orders SET status = %s WHERE order_id = %s", (new_status, order_id))
        d.connect.commit()
        QMessageBox.information(self, "Успех", f"Статус заказа #{order_id} изменён на '{new_status}'")
        self.load_orders()


class ClientWindow(BaseWindow):
    def __init__(self, user):
        super().__init__()
        self.user = user
        self.selected_product = None
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Окно для Клиента")
        self.ui.label_user.setText(f"Пользователь: {user['full_name']}")

        self.ui.tabWidget.removeTab(2)
        for w in (self.ui.pushButton_editStatus, self.ui.comboBox_new_stat,
                  self.ui.label_3, self.ui.comboBox_sorting_stat):
            w.hide()

        self.load_categories("Все")
        self.ui.comboBox_sorting.currentIndexChanged.connect(self.load_data)
        self.load_data()
        self.load_delivery()
        self.load_client_orders()

        self.ui.comboVariant.currentIndexChanged.connect(self.update_total)
        self.ui.spinQuantity.valueChanged.connect(self.update_total)
        self.ui.comboDelivery.currentIndexChanged.connect(self.update_total)
        self.ui.pushButton_CreateOrder.clicked.connect(self.create_order)
        self.ui.pushButton_cancelOrder.clicked.connect(self.cancel_order)
        self.ui.pushButton_logout.clicked.connect(self.go_back)

    def add_card_extra(self, layout, product):
        btn = QPushButton("Выбрать")
        btn.clicked.connect(lambda _, p=product: self.select_product(p))
        layout.addWidget(btn)

    def select_product(self, product):
        self.selected_product = product
        self.ui.label_SelectedProduct.setText(f"{product['name']} | {product['sku']}")
        d = db()
        d.cursor.execute("SELECT * FROM product_variants WHERE product_id = %s", (product['product_id'],))
        self.ui.comboVariant.clear()
        for v in d.cursor.fetchall():
            self.ui.comboVariant.addItem(
                f"{v['size']} / {v['color']} (в наличии: {v['stock_qty']})", v
            )
        self.update_total()

    def load_delivery(self):
        d = db()
        d.cursor.execute("SELECT * FROM delivery_methods")
        for m in d.cursor.fetchall():
            self.ui.comboDelivery.addItem(
                f"{m['name']} — {m['cost']} ₽ ({m['delivery_days']} дн.)", m
            )

    def update_total(self):
        if not self.selected_product:
            return
        variant = self.ui.comboVariant.currentData()
        delivery = self.ui.comboDelivery.currentData()
        if not variant or not delivery:
            return
        base_price = float(self.selected_product['price'])
        modifier = float(variant['price_modifier'])
        discount = int(self.selected_product['discount'])
        price_with_modifier = base_price + modifier
        price_with_discount = price_with_modifier * (1 - discount / 100)
        total = price_with_discount * self.ui.spinQuantity.value() + float(delivery['cost'])
        self.ui.label_TotalValue.setText(f"{total:.2f} ₽")

    def create_order(self):
        if not self.selected_product:
            QMessageBox.warning(self, "Ошибка", "Выберите товар")
            return
        address = self.ui.editShippingAddress.text()
        if not address:
            QMessageBox.warning(self, "Ошибка", "Укажите адрес доставки")
            return

        variant = self.ui.comboVariant.currentData()
        delivery = self.ui.comboDelivery.currentData()
        qty = self.ui.spinQuantity.value()
        base_price = float(self.selected_product['price'])
        modifier = float(variant['price_modifier'])
        discount = int(self.selected_product['discount'])
        price_with_modifier = base_price + modifier
        price_with_discount = price_with_modifier * (1 - discount / 100)
        total = price_with_discount * qty + float(delivery['cost'])

        d = db()
        d.cursor.execute("""
            INSERT INTO orders (user_id, total_amount, status, address, delivery_method_id)
            VALUES (%s, %s, 'новый', %s, %s)
        """, (self.user['user_id'], total, address, delivery['delivery_method_id']))
        d.connect.commit()
        order_id = d.cursor.lastrowid

        d.cursor.execute("""
            INSERT INTO order_items (order_id, variant_id, quantity, price_at_order)
            VALUES (%s, %s, %s, %s)
        """, (order_id, variant['variant_id'], qty, price_with_discount))
        d.connect.commit()

        QMessageBox.information(self, "Успех", f"Заказ #{order_id} оформлен!")
        self.load_client_orders()

    def load_client_orders(self):
        d = db()
        d.cursor.execute("""
            SELECT o.order_id, p.name, pv.size, pv.color,
                   oi.quantity, o.total_amount, o.status, o.order_date
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN product_variants pv ON oi.variant_id = pv.variant_id
            JOIN products p ON pv.product_id = p.product_id
            WHERE o.user_id = %s
            ORDER BY o.order_date DESC
        """, (self.user['user_id'],))
        self.fill_table(self.ui.tableWidget_orders, d.cursor.fetchall())

    def cancel_order(self):
        row = self.ui.tableWidget_orders.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        order_id = self.ui.tableWidget_orders.item(row, 0).text()
        status = self.ui.tableWidget_orders.item(row, 6).text()
        if status not in ("новый", "обработка"):
            QMessageBox.warning(self, "Ошибка", f"Нельзя отменить заказ со статусом: {status}")
            return
        d = db()
        d.cursor.execute("UPDATE orders SET status = 'отменено' WHERE order_id = %s", (order_id,))
        d.connect.commit()
        QMessageBox.information(self, "Успех", f"Заказ #{order_id} отменён")
        self.load_client_orders()


class GuestWindow(BaseWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle('Каталог для гостя')
        self.ui.label_user.setText("Пользователь: Гость")

        for w in (self.ui.groupSelection_2, self.ui.groupOrder_2, self.ui.comboBox_sorting):
            w.hide()
        self.ui.tabWidget.removeTab(2)
        self.ui.tabWidget.removeTab(1)

        d = db()
        d.cursor.execute('SELECT * FROM products')
        for product in d.cursor.fetchall():
            self.add_card(product)

        self.ui.pushButton_logout.clicked.connect(self.go_back)


if __name__ == "__main__":
    app = QApplication([])
    apply_stylesheet(app, theme='dark_purple.xml')
    myFont = QtGui.QFont("Comic Sans MS")
    myFont.setPointSize(12)  # Устанавливаем размер
    QApplication.setFont(myFont)
    window = LoginWindow()
    window.show()
    app.exec()




