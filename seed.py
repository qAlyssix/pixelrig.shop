from app import app, db, Component, Computer

components_data = [
    ('Процессор', 'Intel Core i3-12100F', 10900),
    ('Процессор', 'AMD Ryzen 5 7600', 18400),
    ('Процессор', 'AMD Ryzen 7 7800X3D', 32300),

    ('Материнская плата', 'MSI PRO B760M-A', 11000),
    ('Материнская плата', 'ASUS TUF GAMING B650-PLUS', 19000),
    ('Материнская плата', 'ASUS ROG STRIX X670E-E', 45000),

    ('Видеокарта', 'GeForce RTX 5060 8 ГБ', 53300),
    ('Видеокарта', 'GeForce RTX 5070 12 ГБ', 94200),
    ('Видеокарта', 'GeForce RTX 5080 16 ГБ', 171000),

    ('Оперативная память', '16 ГБ DDR5 5600 МГц', 22000),
    ('Оперативная память', '32 ГБ DDR5 5600 МГц', 45000),
    ('Оперативная память', '64 ГБ DDR5 6000 МГц', 130000),

    ('Накопитель', 'SSD NVMe 500 ГБ', 10600),
    ('Накопитель', 'SSD NVMe 1 ТБ', 16500),
    ('Накопитель', 'SSD NVMe 2 ТБ', 31000),

    ('Блок питания', '550 Вт 80+ Bronze', 5000),
    ('Блок питания', '750 Вт 80+ Gold', 9000),
    ('Блок питания', '1000 Вт 80+ Gold', 15000),

    ('Корпус', 'Mid-Tower базовый', 4000),
    ('Корпус', 'Mid-Tower со стеклом', 7000),
    ('Корпус', 'Full-Tower с подсветкой', 14000),

    ('Охлаждение', 'Башенный кулер 120 мм', 2500),
    ('Охлаждение', 'Башенный кулер 2x120 мм', 5000),
    ('Охлаждение', 'Водяное охлаждение 360 мм', 12000),
]

computers_data = [
    (
        'Старт',
        'Недорогой компьютер для учёбы и популярных игр в Full HD.',
        'start.jpg',
        ['Intel Core i3-12100F', 'MSI PRO B760M-A', 'GeForce RTX 5060 8 ГБ',
         '16 ГБ DDR5 5600 МГц', 'SSD NVMe 500 ГБ', '550 Вт 80+ Bronze',
         'Mid-Tower базовый', 'Башенный кулер 120 мм'],
    ),
    (
        'Оптима',
        'Сбалансированный игровой ПК для современных игр на высоких настройках.',
        'optima.jpg',
        ['AMD Ryzen 5 7600', 'ASUS TUF GAMING B650-PLUS', 'GeForce RTX 5070 12 ГБ',
         '32 ГБ DDR5 5600 МГц', 'SSD NVMe 1 ТБ', '750 Вт 80+ Gold',
         'Mid-Tower со стеклом', 'Башенный кулер 2x120 мм'],
    ),
    (
        'Максимум',
        'Топовая сборка для игр в 4K, стриминга и работы с видео.',
        'maximum.jpg',
        ['AMD Ryzen 7 7800X3D', 'ASUS ROG STRIX X670E-E', 'GeForce RTX 5080 16 ГБ',
         '64 ГБ DDR5 6000 МГц', 'SSD NVMe 2 ТБ', '1000 Вт 80+ Gold',
         'Full-Tower с подсветкой', 'Водяное охлаждение 360 мм'],
    ),
]


with app.app_context():
    if Component.query.first():
        print('База уже заполнена, ничего не добавляю.')
    else:
        for category, name, price in components_data:
            db.session.add(Component(category=category, name=name, price=price))
        db.session.commit()

        for name, description, image, part_names in computers_data:
            computer = Computer(name=name, description=description,
                                image=image, is_custom=False)
            for part_name in part_names:
                part = Component.query.filter_by(name=part_name).first()
                computer.components.append(part)
            db.session.add(computer)
        db.session.commit()

        print(f'Добавлено комплектующих: {Component.query.count()}')
        print(f'Добавлено компьютеров: {Computer.query.count()}')