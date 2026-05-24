from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from db import Database
from main_window_ui import Ui_MainWindow
from упрощенный import LoginWindow


class ManagerWindow(QMainWindow):
    def __init__(self,user):
        super().__init__()
        self.user = user
        self.ui =Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.groupOrder_2.hide()
        self.ui.groupSelection_2.hide()

        self.load_categories()
        self.ui.comboBox_sorting.currentIndexChanged.connect(self.load_data)

        self.load_status()
        self.ui.comboBox_sorting_stat.currentIndexChanged.connect(self.load_orders)

        self.load_data()
        self.load_orders()
        self.ui.pushButton_logout.clicked.connect(self.go_back)

    def load_categories(self):
        db = Database()
        db.cursor.execute('select * from Categories')
        categories = db.cursor.fetchall()

        self.ui.comboBox_sorting.addItem('всее', 0)
        for cat in categories:
            self.ui.comboBox_sorting.addItem(cat['category_name'], cat['category_id'])

    def load_data(self):
        while self.ui.verticalLayout_card.count():
            item = self.ui.verticalLayout_card.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        category_id = self.ui.comboBox_sorting.currentData()

        db = Database()
        if category_id == 0:
            db.cursor.execute('select * from Products')
        else:
            db.cursor.execute('select * from Products where category_id = %s', (category_id,))

        products = db.cursor.fetchall()
        for product in products:
            self.add_card(product)

    def add_card(self, product):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(frame)

        photo = QLabel()
        photo.setFixedSize(80,80)
        path = product['image_path'] or "zagl.png"
        pixmap = QPixmap(path)
        photo.setPixmap(pixmap.scaled(80, 80))
        layout.addWidget(photo)

        info = QLabel(f"{product['name']} | {product['sku']}\n"
        f"Описание: {product['description']}\n"
        f"{product['composition']}\n"
        f"Цена: {product['price']}")
        layout.addWidget(info)

        discount = QLabel(f"Скидка: \n {product['discount']}%")
        discount.setFixedSize(80,80)
        layout.addWidget(discount)

        self.ui.verticalLayout_card.addWidget(frame)

    def load_status(self):
        db = Database()
        db.cursor.execute('select DISTINCT status from Orders')
        status = db.cursor.fetchall()

        self.ui.comboBox_sorting_stat.addItem('все статусы', 0)
        for s in status:
            self.ui.comboBox_sorting_stat.addItem(s['status'],s['status'])

    def load_orders(self):
        status = self.ui.comboBox_sorting_stat.currentData()

        db = Database()
        if status == 0:
            db.cursor.execute("""SELECT o.order_id, u.username, p.name, pv.size, pv.color,
                   oi.quantity, o.total_amount, o.status, o.order_date
            FROM Orders o
            JOIN Users u ON o.user_id = u.user_id
            JOIN OrderItems oi ON o.order_id = oi.order_id
            JOIN ProductVariants pv ON oi.variant_id = pv.variant_id
            JOIN Products p ON pv.product_id = p.product_id
            """)
        else:
            db.cursor.execute("""SELECT o.order_id, u.username, p.name, pv.size, pv.color,
                               oi.quantity, o.total_amount, o.status, o.order_date
                        FROM Orders o
                        JOIN Users u ON o.user_id = u.user_id
                        JOIN OrderItems oi ON o.order_id = oi.order_id
                        JOIN ProductVariants pv ON oi.variant_id = pv.variant_id
                        JOIN Products p ON pv.product_id = p.product_id
                        WHERE o.status = %s""", (status,))

        orders = db.cursor.fetchall()
        self.ui.tableWidget_orders.setRowCount(str(orders))
        for row, order in enumerate(orders):
            for col, value in enumerate(order.values()):
                self.ui.tableWidget_orders.setItem(row, col, QTableWidgetItem(len(value)))

    def update_status_order(self):
        row = self.ui.tableWidget_orders.currentRow()
        if row == -1:
            QMessageBox.warning(self, '','')

        order_id = self.ui.tableWidget_orders.item()

    def go_back(self):
        self.b = LoginWindow()
        self.b.show()
        self.close()

