# telegram - бот для регистрации

Создан для Пионерского выезда 2024

## Запуск

Перед запуском необходимо правильно настроить `.env` файл, основываясь на `.env.example`, чтобы запустить именно своего бота и подключиться к своей Google-таблице.

После подготовки можно использовать следующие команды (имея установленный `make`):

`make install` - установка зависимостей

`make run` - запуск бота локально

`make docker-build` - сборка docker-образа с ботом

`make docker-run` - запуск бота в docker-окружении

`make docker-stop` - остановка бота в docker-окружении

`make docker-remove` - удаление docker-контейнера

`make docker-clean` - удаление docker-контейнера и docker-образа

# Требования

Требования, написаные мной же

## Формальные требования к системе регистрации для участия в выезде

### Общие требования
1. Регистрация участников для выезда осуществляется через Telegram-бот.
2. Система должна обеспечивать хранение данных зарегистрированных участников в соответствующем хранилище (например, файл, таблица или база данных).
3. Все взаимодействия с участниками и администраторами проходят через функционал Telegram-бота.

### Функциональные требования для участника
1. **Регистрация**:
   - Каждый участник должен иметь возможность зарегистрироваться через Telegram-бота, предоставив следующие данные:
     - ФИО (фамилия, имя, отчество);
     - дата рождения;
     - учебная группа;
     - номер телефона;
     - никнейм в Telegram.
   - Система должна обеспечивать уникальность регистрации: один участник может зарегистрироваться только один раз.

2. **Редактирование данных**:
   - После регистрации участник должен иметь возможность в любой момент изменить свои данные (например, в случае ошибок при первоначальной регистрации).
   
3. **Подтверждение регистрации**:
   - После предоставления данных, участник должен получить уведомление или форму подтверждения (с использованием кнопок или иных элементов интерфейса Telegram-бота).

### Функциональные требования для администратора (организатора)
1. **Просмотр зарегистрированных участников**:
   - Администраторы должны иметь доступ к актуальному списку всех зарегистрированных участников.
   - Данный список должен содержать полную информацию о каждом участнике: ФИО, дату рождения, учебную группу, номер телефона и ник в Telegram.

2. **Управление хранилищем данных**:
   - Администраторы должны иметь возможность просматривать и, при необходимости, экспортировать данные из хранилища.

### Требования к серверу (Telegram-бот)
1. **Регистрация и обработка данных**:
   - Сервер должен обрабатывать запросы от участников на регистрацию, проверять на наличие повторной регистрации и сохранять предоставленные данные в хранилище.
   
2. **Обновление данных**:
   - Сервер должен позволять участникам обновлять свою информацию, перезаписывая соответствующие данные в хранилище.

3. **Уведомления и подтверждение**:
   - Сервер должен уметь отправлять уведомления или формы с подтверждающими кнопками участникам для подтверждения или изменения их данных.

4. **Управление данными участников**:
   - Сервер должен предоставлять администратору интерфейс (например, команду в Telegram-боте) для доступа к списку зарегистрированных участников.

### Требования к клиенту (участник)
1. **Регистрация через Telegram**:
   - Клиент (участник) должен зарегистрироваться с использованием Telegram-бота, предоставив свои данные, которые запрашивает бот.
   
2. **Редактирование данных**:
   - Клиент должен иметь возможность отправить запрос на изменение своих данных через Telegram-бота.

3. **Получение уведомлений**:
   - Клиент должен получать от Telegram-бота уведомления о регистрации, успешной модификации данных и других важных сообщениях.

### Требования к администратору
1. **Просмотр и управление данными**:
   - Администратор должен иметь возможность просматривать полный список зарегистрированных участников и управлять этим списком через Telegram-бота.
   
2. **Использование функционала бота**:
   - Администратор должен использовать Telegram-бота для всех операций, связанных с управлением участниками и контролем за регистрацией.