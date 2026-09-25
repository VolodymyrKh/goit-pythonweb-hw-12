# goit-pythonweb-hw-10

REST API для зберігання та управління контактами з аутентифікацією користувачів.
Стек: **FastAPI**, **SQLAlchemy 2.0 (async)**, **PostgreSQL**, **Pydantic**, **Alembic**, **JWT**,
**Cloudinary**, **Docker Compose**, пакетний менеджер **uv**.

## Можливості

- Реєстрація та вхід користувачів, пароль зберігається лише у вигляді хешу (Argon2).
- Авторизація через JWT `access_token`: усі операції з контактами доступні лише зареєстрованим користувачам.
- Кожен користувач бачить і змінює лише власні контакти.
- Верифікація email: після реєстрації надсилається лист із посиланням для підтвердження.
- Обмеження кількості запитів до `/api/users/me` (10 на хвилину).
- CORS.
- Оновлення аватара користувача через Cloudinary.

## Структура

```
├── src
│   ├── api
│   │   ├── auth.py          # реєстрація, логін, підтвердження email
│   │   ├── users.py         # /me, оновлення аватара
│   │   ├── contacts.py      # маршрути /api/contacts
│   │   └── utils.py         # /api/healthchecker
│   ├── services
│   │   ├── auth.py          # хешування паролів, JWT, поточний користувач
│   │   ├── users.py         # бізнес-логіка користувачів
│   │   ├── contacts.py      # бізнес-логіка контактів
│   │   ├── email.py         # надсилання листів (fastapi-mail)
│   │   ├── upload_file.py   # завантаження аватарів у Cloudinary
│   │   ├── limiter.py       # rate limiter (slowapi)
│   │   └── templates        # HTML-шаблон листа
│   ├── repository
│   │   ├── users.py         # запити до БД для користувачів
│   │   └── contacts.py      # запити до БД для контактів
│   ├── database
│   │   ├── models.py        # моделі User і Contact
│   │   └── db.py            # async-сесія SQLAlchemy
│   ├── conf
│   │   └── config.py        # налаштування з .env
│   └── schemas.py           # Pydantic-схеми
├── migrations               # міграції Alembic
├── Dockerfile
├── docker-compose.yml       # застосунок, PostgreSQL, Mailpit
├── pyproject.toml
└── main.py
```

## Запуск через Docker Compose

1. Створити `.env` на основі `.env.example` і заповнити значення
   (пароль БД, `JWT_SECRET`, ключі Cloudinary):
   ```bash
   cp .env.example .env
   ```
2. Запустити всі сервіси:
   ```bash
   docker compose up -d --build
   ```
   Міграції застосовуються автоматично під час старту контейнера `app`.

| Сервіс     | Адреса                          |
|------------|---------------------------------|
| API        | http://localhost:8000           |
| Swagger    | http://localhost:8000/docs      |
| ReDoc      | http://localhost:8000/redoc     |
| Mailpit    | http://localhost:8025 (листи)   |
| PostgreSQL | `localhost:5432`                |

За замовчуванням листи потрапляють у локальний **Mailpit**, їх можна переглянути у веб-інтерфейсі.
Щоб надсилати справжні листи, вкажіть у `.env` параметри свого SMTP-сервера (див. коментарі в `.env.example`).

### Локальний запуск без контейнера застосунку

```bash
uv sync
docker compose up -d postgres mailpit
uv run alembic upgrade head
uv run python main.py
```

## Як користуватися

1. `POST /api/auth/register` створює користувача (201). Якщо email або username уже зайняті, повертається 409.
2. Відкрити лист у Mailpit і перейти за посиланням `GET /api/auth/confirmed_email/{token}`.
3. `POST /api/auth/login` приймає форму з полями `username` і `password` та повертає `access_token`.
   Якщо користувача немає, пароль не збігається або email не підтверджено, повертається 401.
4. Передавати токен у заголовку `Authorization: Bearer <access_token>`.
   У Swagger для цього є кнопка **Authorize**.

## Ендпоінти

### Аутентифікація

| Метод | Шлях                                 | Опис                                     |
|-------|--------------------------------------|------------------------------------------|
| POST  | `/api/auth/register`                 | Реєстрація (201, 409)                    |
| POST  | `/api/auth/login`                    | Вхід, повертає `access_token` (401)      |
| GET   | `/api/auth/confirmed_email/{token}`  | Підтвердження email                      |
| POST  | `/api/auth/request_email`            | Повторно надіслати лист підтвердження    |

### Користувачі (потрібен токен)

| Метод | Шлях                 | Опис                                           |
|-------|----------------------|------------------------------------------------|
| GET   | `/api/users/me`      | Поточний користувач (не більше 10 запитів/хв)  |
| PATCH | `/api/users/avatar`  | Оновити аватар (файл-зображення, до 5 МБ)      |

### Контакти (потрібен токен)

| Метод  | Шлях                        | Опис                                              |
|--------|-----------------------------|---------------------------------------------------|
| GET    | `/api/contacts/`            | Список контактів (+ пошук, пагінація)             |
| GET    | `/api/contacts/birthdays`   | Дні народження на найближчі 7 днів (`?days=N`)    |
| GET    | `/api/contacts/{id}`        | Один контакт                                      |
| POST   | `/api/contacts/`            | Створити контакт (201)                            |
| PUT    | `/api/contacts/{id}`        | Оновити контакт (передаються лише змінені поля)   |
| DELETE | `/api/contacts/{id}`        | Видалити контакт                                  |

Query-параметри пошуку для `GET /api/contacts/`: `first_name`, `last_name`, `email`
(частковий збіг без урахування регістру), а також `skip` і `limit`.

### Інше

| Метод | Шлях                  | Опис                          |
|-------|-----------------------|-------------------------------|
| GET   | `/api/healthchecker`  | Перевірка підключення до БД   |

### Приклад тіла запиту для контакту

```json
{
  "first_name": "Volodymyr",
  "last_name": "Kheroim",
  "email": "volodymyr_kh@example.com",
  "phone": "+380501234567",
  "birthday": "1990-09-27",
  "additional_data": "Bro"
}
```
