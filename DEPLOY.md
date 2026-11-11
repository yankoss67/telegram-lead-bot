# Размещение бота на сервере (Ubuntu)

Подходит для любого VPS: Oracle Cloud Always Free, Google Cloud e2-micro, платного VPS за 2–5 €/мес.

## 1. Подключиться к серверу

```bash
ssh -i путь/к/ключу.key ubuntu@IP_СЕРВЕРА
```

## 2. Установить Python и загрузить проект

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip git
git clone https://github.com/ВАШ_ЛОГИН/telegram-lead-bot.git lead_bot
cd lead_bot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

Если проекта нет на GitHub, загрузите его с компьютера:
`scp -i ключ.key -r lead_bot ubuntu@IP_СЕРВЕРА:~/`

## 3. Создать .env на сервере

```bash
cp .env.example .env
nano .env        # вписать токен и ID, сохранить: Ctrl+O, Enter, выйти: Ctrl+X
```

## 4. Проверить запуск вручную

```bash
venv/bin/python bot.py
```

Напишите боту /start. Если всё работает, остановите бота: Ctrl+C.

⚠️ Бот с одним токеном может работать только в одном месте. Перед запуском на сервере остановите его на компьютере, иначе будет `TelegramConflictError`.

## 5. Включить автозапуск

```bash
sudo cp deploy/leadbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now leadbot
```

Теперь бот работает круглосуточно, сам поднимается после перезагрузки сервера и после ошибок. Терминал можно закрывать.

## Полезные команды

| Что сделать | Команда |
|---|---|
| Статус бота | `sudo systemctl status leadbot` |
| Логи в реальном времени | `journalctl -u leadbot -f` |
| Перезапуск | `sudo systemctl restart leadbot` |
| Остановка | `sudo systemctl stop leadbot` |
| Обновить код из GitHub | `git pull && sudo systemctl restart leadbot` |
| Скачать базу заявок себе | `scp -i ключ.key ubuntu@IP:~/lead_bot/leads.db .` |
