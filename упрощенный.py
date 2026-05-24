from db import Database
from login_ui import Ui_Login
from main_window_ui import Ui_MainWindow
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

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
        for cat in db().cursor.execute('SELECT * FROM Categories') or []:
            self.ui.comboBox_sorting.addItem(cat['category_name'], cat['category_id'])

    def load_data(self):
        self.clear_cards()
        cid = self.ui.comboBox_sorting.currentData()
        cur = db().cursor
        if cid == 0:
            cur.execute('SELECT * FROM Products')
        else:
            cur.execute('SELECT * FROM Products WHERE category_id = %s', (cid,))
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
            f"{product['composition']}\n"
            f"Цена: {product['price']}"
        ))

        disc = QLabel(f"Скидка: \n {product['discount']}%")
        disc.setFixedSize(80, 80)
        layout.addWidget(disc)

        self.add_card_extra(layout, product)  # хук для доп. виджетов
        self.ui.verticalLayout_card.addWidget(frame)

    def add_card_extra(self, layout, product):
        pass  # переопределяется в подклассах при необходимости


class LoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Login()
        self.ui.setupUi(self)
        self.setWindowTitle('Магазин одежды "Сельгира"')
        self.ui.pushButton_guest.clicked.connect(self.go_guest)
        self.ui.pushButton_login.clicked.connect(self.handle_login)

    def handle_login(self):
        login = self.ui.lineEdit_login.text()
        password = self.ui.lineEdit_password.text()
        cur = db().cursor
        cur.execute('SELECT * FROM Users WHERE username = %s AND password_hash = %s', (login, password))
        user = cur.fetchone()
        if user:
            self.main = ClientWindow(user) if user['role_id'] == 2 else ManagerWindow(user)
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
        self.ui.label_user.setText("Пользователь: Менеджер")

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

        self.ui.comboBox_new_stat.addItems(["Новый", "В обработке", "Доставлен", "Возврат", "Отменён"])
        self.ui.pushButton_editStatus.clicked.connect(self.update_order_status)
        self.ui.pushButton_logout.clicked.connect(self.go_back)

    def load_categories(self, all_label="Все товары"):
        d = db()
        d.cursor.execute('SELECT * FROM Categories')
        self.ui.comboBox_sorting.addItem(all_label, 0)
        for cat in d.cursor.fetchall():
            self.ui.comboBox_sorting.addItem(cat['category_name'], cat['category_id'])

    def load_status(self):
        d = db()
        d.cursor.execute('SELECT DISTINCT status FROM Orders')
        self.ui.comboBox_sorting_stat.addItem("Все", "")
        for s in d.cursor.fetchall():
            self.ui.comboBox_sorting_stat.addItem(s['status'], s['status'])

    def load_orders(self):
        status = self.ui.comboBox_sorting_stat.currentData()
        d = db()
        query = """SELECT o.order_id, u.username, p.name, pv.size, pv.color,
                          oi.quantity, o.total_amount, o.status, o.order_date
                   FROM Orders o
                   JOIN Users u ON o.user_id = u.user_id
                   JOIN OrderItems oi ON o.order_id = oi.order_id
                   JOIN ProductVariants pv ON oi.variant_id = pv.variant_id
                   JOIN Products p ON pv.product_id = p.product_id"""
        d.cursor.execute(query if status == "" else query + " WHERE o.status = %s", () if status == "" else (status,))
        self.fill_table(self.ui.tableWidget_orders, d.cursor.fetchall())

    def update_order_status(self):
        row = self.ui.tableWidget_orders.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        order_id = self.ui.tableWidget_orders.item(row, 0).text()
        new_status = self.ui.comboBox_new_stat.currentText()
        d = db()
        d.cursor.execute("UPDATE Orders SET status = %s WHERE order_id = %s", (new_status, order_id))
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
        self.ui.label_user.setText(f"Пользователь: Клиент {user['username']}")

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
        self.ui.pushButton_CreateOrder.clicked.connect(self.create_order)
        self.ui.pushButton_cancelOrder.clicked.connect(self.cancel_order)
        self.ui.pushButton_logout.clicked.connect(self.go_back)

    def load_categories(self, all_label="Все"):
        d = db()
        d.cursor.execute('SELECT * FROM Categories')
        self.ui.comboBox_sorting.addItem(all_label, 0)
        for cat in d.cursor.fetchall():
            self.ui.comboBox_sorting.addItem(cat['category_name'], cat['category_id'])

    def add_card_extra(self, layout, product):
        btn = QPushButton("Выбрать")
        btn.clicked.connect(lambda _, p=product: self.select_product(p))
        layout.addWidget(btn)

    def select_product(self, product):
        self.selected_product = product
        self.ui.label_SelectedProduct.setText(f"{product['name']} | {product['sku']}")
        d = db()
        d.cursor.execute("SELECT * FROM ProductVariants WHERE product_id = %s", (product['product_id'],))
        self.ui.comboVariant.clear()
        for v in d.cursor.fetchall():
            self.ui.comboVariant.addItem(f"{v['size']} / {v['color']} (в наличии: {v['quantity_in_stock']})", v)
        self.update_total()

    def load_delivery(self):
        d = db()
        d.cursor.execute("SELECT * FROM DeliveryMethods")
        for m in d.cursor.fetchall():
            self.ui.comboDelivery.addItem(f"{m['name']} — {m['base_cost']} ₽", m)

    def update_total(self):
        if not self.selected_product:
            return
        variant = self.ui.comboVariant.currentData()
        delivery = self.ui.comboDelivery.currentData()
        if not variant or not delivery:
            return
        price = float(self.selected_product['price']) + float(variant['additional_price'])
        total = price * self.ui.spinQuantity.value() + float(delivery['base_cost'])
        self.ui.label_TotalValue.setText(f"{total:.2f} ₽")

    def create_order(self):
        if not self.selected_product:
            QMessageBox.warning(self, "Ошибка", "Выберите товар")
            return
        shipping = self.ui.editShippingAddress.text()
        if not shipping:
            QMessageBox.warning(self, "Ошибка", "Укажите адрес доставки")
            return

        variant = self.ui.comboVariant.currentData()
        delivery = self.ui.comboDelivery.currentData()
        qty = self.ui.spinQuantity.value()
        price = float(self.selected_product['price']) + float(variant['additional_price'])
        total = price * qty + float(delivery['base_cost'])

        d = db()
        d.cursor.execute("""
            INSERT INTO Orders (user_id, total_amount, status, shipping_address, billing_address, delivery_method_id)
            VALUES (%s, %s, 'Новый', %s, %s, %s)
        """, (self.user['user_id'], total, shipping, self.ui.editBillingAddress.text(), delivery['delivery_method_id']))
        d.connect.commit()
        order_id = d.cursor.lastrowid

        d.cursor.execute("""
            INSERT INTO OrderItems (order_id, variant_id, quantity, price_at_order)
            VALUES (%s, %s, %s, %s)
        """, (order_id, variant['variant_id'], qty, price))
        d.connect.commit()

        QMessageBox.information(self, "Успех", f"Заказ #{order_id} оформлен!")
        self.load_client_orders()

    def load_client_orders(self):
        d = db()
        d.cursor.execute("""
            SELECT o.order_id, p.name, pv.size, pv.color,
                   oi.quantity, o.total_amount, o.status, o.order_date
            FROM Orders o
            JOIN OrderItems oi ON o.order_id = oi.order_id
            JOIN ProductVariants pv ON oi.variant_id = pv.variant_id
            JOIN Products p ON pv.product_id = p.product_id
            WHERE o.user_id = %s
        """, (self.user['user_id'],))
        self.fill_table(self.ui.tableWidget_orders, d.cursor.fetchall())

    def cancel_order(self):
        row = self.ui.tableWidget_orders.currentRow()
        if row == -1:
            QMessageBox.warning(self, "Ошибка", "Выберите заказ")
            return
        order_id = self.ui.tableWidget_orders.item(row, 0).text()
        status = self.ui.tableWidget_orders.item(row, 6).text()
        if status not in ("Новый", "В обработке"):
            QMessageBox.warning(self, "Ошибка", f"Нельзя отменить заказ со статусом: {status}")
            return
        d = db()
        d.cursor.execute("UPDATE Orders SET status = 'Отменён' WHERE order_id = %s", (order_id,))
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
        d.cursor.execute('SELECT * FROM Products')
        for product in d.cursor.fetchall():
            self.add_card(product)

        self.ui.pushButton_logout.clicked.connect(self.go_back)


if __name__ == "__main__":
    app = QApplication([])
    window = LoginWindow()
    window.show()
    app.exec()