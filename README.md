# goit-pythonweb-hw-12

REST API для зберігання та управління контактами з аутентифікацією, ролями та кешуванням.
Стек: **FastAPI**, **SQLAlchemy 2.0 (async)**, **PostgreSQL**, **Redis**, **Pydantic**, **Alembic**, **JWT**,
**Cloudinary**, **Docker Compose**, **pytest**, **Sphinx**, пакетний менеджер **uv**.

## Можливості

- Реєстрація та вхід користувачів, пароль зберігається лише у вигляді хешу (Argon2).
- Пара токенів: короткий `access_token` (15 хв) і `refresh_token` (7 днів) з ротацією.
  Кожен refresh-токен можна використати лише один раз, у базі зберігається тільки його хеш.
- Кожен користувач бачить і змінює лише власні контакти.
- Верифікація email: після реєстрації надсилається лист із посиланням для підтвердження.
- Скидання пароля через email: одноразове посилання, дійсне годину. Після скидання refresh-токен відкликається.
- Ролі `user` та `admin`. Змінювати свій аватар (Cloudinary) і ролі інших користувачів можуть лише адміністратори.
- Поточний користувач кешується в Redis: `get_current_user` не звертається до БД на кожен запит.
  У кеш потрапляють лише публічні поля (без хешу пароля), запис живе 15 хвилин
  і видаляється при будь-якій зміні користувача. Якщо Redis недоступний, дані беруться з БД.
- Обмеження кількості запитів до `/api/users/me` (10 на хвилину), CORS.
- Документація коду (Sphinx), модульні та інтеграційні тести з покриттям 99%.

## Структура

```
├── src
│   ├── api
│   │   ├── auth.py          # реєстрація, логін, токени, email, скидання пароля
│   │   ├── users.py         # /me, аватар, ролі
│   │   ├── contacts.py      # маршрути /api/contacts
│   │   └── utils.py         # /api/healthchecker
│   ├── services
│   │   ├── auth.py          # хешування паролів, JWT, поточний користувач, перевірка ролі
│   │   ├── cache.py         # кеш користувача в Redis
│   │   ├── users.py         # бізнес-логіка користувачів
│   │   ├── contacts.py      # бізнес-логіка контактів
│   │   ├── email.py         # надсилання листів (fastapi-mail)
│   │   ├── upload_file.py   # завантаження аватарів у Cloudinary
│   │   ├── limiter.py       # rate limiter (slowapi)
│   │   └── templates        # HTML-шаблони листів і форми нового пароля
│   ├── repository
│   │   ├── users.py         # запити до БД для користувачів
│   │   └── contacts.py      # запити до БД для контактів
│   ├── database
│   │   ├── models.py        # моделі User і Contact, ролі
│   │   └── db.py            # async-сесія SQLAlchemy
│   ├── scripts
│   │   └── set_role.py      # CLI для призначення ролі (перший адміністратор)
│   ├── conf
│   │   └── config.py        # налаштування з .env
│   └── schemas.py           # Pydantic-схеми
├── tests
│   ├── conftest.py          # фікстури: SQLite у пам'яті, fakeredis, заглушки пошти
│   ├── unit                 # модульні тести (репозиторії, сервіси, скрипти)
│   └── integration          # інтеграційні тести маршрутів
├── docs                     # документація Sphinx
├── migrations               # міграції Alembic
├── Dockerfile
├── docker-compose.yml       # застосунок, PostgreSQL, Redis, Mailpit
├── pyproject.toml
└── main.py
```

## Запуск через Docker Compose

1. Створити `.env` на основі `.env.example` і заповнити значення
   (пароль БД, `JWT_SECRET`, `REDIS_PASSWORD`, ключі Cloudinary):
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
| Redis      | `localhost:6379` (лише з цього комп'ютера) |

За замовчуванням листи потрапляють у локальний **Mailpit**, їх можна переглянути у веб-інтерфейсі.
Щоб надсилати справжні листи, вкажіть у `.env` параметри свого SMTP-сервера (див. коментарі в `.env.example`).

### Призначення адміністратора

Змінювати ролі через API може лише адміністратор, тому першого адміністратора призначають з командного рядка:

```bash
docker compose exec app uv run --no-sync python -m src.scripts.set_role <username> admin
```

Далі адміністратор може змінювати ролі інших користувачів через `PATCH /api/users/{user_id}/role`.

### Локальний запуск без контейнера застосунку

```bash
uv sync
docker compose up -d postgres redis mailpit
uv run alembic upgrade head
uv run python main.py
```

## Тести

Тести не потребують запущених сервісів: PostgreSQL замінюється на SQLite у пам'яті,
Redis на fakeredis, а надсилання листів і Cloudinary на заглушки.

```bash
uv run pytest
```

Звіт про покриття (pytest-cov) виводиться автоматично. HTML-звіт можна отримати так:

```bash
uv run pytest --cov-report=html   # відкрити htmlcov/index.html
```

## Документація

```bash
uv run sphinx-build -b html docs docs/_build/html
```

Після збірки відкрити `docs/_build/html/index.html`.

## Як користуватися

1. `POST /api/auth/register` створює користувача (201). Якщо email або username уже зайняті, повертається 409.
2. Відкрити лист у Mailpit і перейти за посиланням `GET /api/auth/confirmed_email/{token}`.
3. `POST /api/auth/login` приймає форму з полями `username` і `password` та повертає
   `access_token` і `refresh_token`. Якщо користувача немає, пароль не збігається або email не підтверджено, повертається 401.
4. Передавати токен у заголовку `Authorization: Bearer <access_token>`.
   У Swagger для цього є кнопка **Authorize**.
5. Коли `access_token` закінчиться, отримати нову пару через `POST /api/auth/refresh`.

**Забули пароль?** `POST /api/auth/request_password_reset` надсилає лист із посиланням.
Воно відкриває сторінку з формою для нового пароля.

## Ендпоінти

### Аутентифікація

| Метод | Шлях                                 | Опис                                           |
|-------|--------------------------------------|------------------------------------------------|
| POST  | `/api/auth/register`                 | Реєстрація (201, 409)                          |
| POST  | `/api/auth/login`                    | Вхід, повертає пару токенів (401)              |
| POST  | `/api/auth/refresh`                  | Нова пара токенів за `refresh_token`           |
| POST  | `/api/auth/logout`                   | Відкликати `refresh_token` (потрібен токен)    |
| GET   | `/api/auth/confirmed_email/{token}`  | Підтвердження email                            |
| POST  | `/api/auth/request_email`            | Повторно надіслати лист підтвердження          |
| POST  | `/api/auth/request_password_reset`   | Надіслати лист для скидання пароля             |
| GET   | `/api/auth/reset_password/{token}`   | Сторінка з формою нового пароля (з листа)      |
| POST  | `/api/auth/reset_password`           | Встановити новий пароль за токеном             |

### Користувачі (потрібен токен)

| Метод | Шлях                          | Доступ | Опис                                           |
|-------|-------------------------------|--------|------------------------------------------------|
| GET   | `/api/users/me`               | усі    | Поточний користувач (не більше 10 запитів/хв)  |
| PATCH | `/api/users/avatar`           | admin  | Оновити аватар (файл-зображення, до 5 МБ)      |
| PATCH | `/api/users/{user_id}/role`   | admin  | Змінити роль користувача (`user` / `admin`)    |

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
