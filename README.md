# UATAC · Бриф продажів

Самооновлюваний дашборд продажів. Живе за адресою
**https://toserhiivynnyk-hash.github.io/uatac-brief/**

Щодня о 07:00 за Києвом GitHub Actions сам тягне дані з KeyCRM, перераховує аналітику,
перебудовує `index.html` і комітить його в цей репозиторій. Через 1–2 хвилини сторінка
за посиланням уже нова. Нічого заливати руками не треба.

---

## Одноразове налаштування (5 хвилин)

### 1. Токен KeyCRM у секрети
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

| Поле | Значення |
|---|---|
| Name | `KEYCRM_TOKEN` |
| Secret | токен KeyCRM (read-only) |

⚠️ **Ніколи неклади токен у код.** Репозиторій публічний (цього вимагає безкоштовний
GitHub Pages), тому все, що в файлах, бачить будь-хто.

### 2. Дозволити Actions комітити
`Settings` → `Actions` → `General` → `Workflow permissions` →
**Read and write permissions** → `Save`

### 3. Увімкнути Pages (якщо ще не увімкнено)
`Settings` → `Pages` → Source: **Deploy from a branch** → Branch: `main` / `(root)` → `Save`

### 4. Ціль місяця (необовʼязково)
`Settings` → `Secrets and variables` → `Actions` → вкладка **Variables** → `New repository variable`

| Name | Value |
|---|---|
| `UATAC_MONTH_TARGET` | наприклад `1200000` |

Якщо змінної немає — ціллю автоматично стає повна виручка минулого місяця.

### 5. Перший запуск
`Actions` → `UATAC Sales Brief` → `Run workflow`. Далі — саме щодня.

---

## Що всередині

| Файл | Що робить |
|---|---|
| `.github/workflows/brief.yml` | розклад і кроки складання |
| `scripts/fetch.py` | тягне 130 днів замовлень з KeyCRM (**тільки GET**) |
| `scripts/analyze.py` | атрибуція по UTM, воронки, прогноз, тригери завдань |
| `scripts/render.py` | збирає HTML із шаблонів |
| `scripts/daily_brief.py` | оркестратор: fetch → analyze → render |
| `templates/` | розмітка, стилі, фронтенд, вбудований Chart.js |
| `playbook.json` | **база знань завдань** — редагуй тут, код не чіпай |
| `decisions.json` | журнал рішень; скрипт сам рахує ефект «до / після» |
| `baseline.json` | база «рік до року»: денні факти за ~540 днів, перебудовується раз на тиждень |
| `spend.json` | витрати на рекламу по місяцях — для MER і точки оптимуму |
| `history.csv` | денний зріз показників — накопичується для довгих трендів |
| `index.html` | те, що бачить команда |

## Як ставиться ціль місяця

Ціль не число з голови, а модель із трьох воріт:

1. **Підлога — рік до року.** `Ціль = той самий місяць торік × (1 + g)`.
   Поки минулий повний місяць не перебив свій торішній, `g = 0` — режим **відновлення**.
   Щойно перебив — вмикається `g = 10%`, режим **зростання**. Перемикається саме.
2. **Стеля — ефективність.** Валова маржа дає беззбитковий MER = `1 / маржа` (зараз ≈ 2.1).
   Нарощуємо бюджет, поки **кожна наступна** гривня приносить більше за цей поріг.
   Далі зростання йде в збиток — це і є «оптимальна ціна вкладених коштів».
3. **Ворота — фізика.** Склад і черга виробництва 2–4 місяці мають витримати потрібний мікс.

Ціль розкладається у формулу, де в кожного множника свій відповідальний:

```
Виручка = Замовлення × Середній чек × (1 − частка скасувань)
```

Бриф показує кожен множник поруч із торішнім і рахує, який чек потрібен при поточному
темпі замовлень, щоб закрити ціль. Так «рости» перетворюється на конкретне число для команди.

Ручне перекриття: змінна `UATAC_MONTH_TARGET`.

## Як додати або змінити завдання

Відкрий `playbook.json` → масив `tasks` → додай обʼєкт:

```json
{
  "id": "унікальний-id",
  "channel": "Google Ads (PMax/Search)",
  "type": "tactical",
  "horizon": "тиждень",
  "owner": "Serhii",
  "title": "Коротка дія одним рядком",
  "trigger": { "kind": "drop", "pct": -25 },
  "why":  ["Чому це важливо, з числами: {rev} ₴ проти {prev_rev} ₴ ({delta}%)."],
  "how":  ["Крок 1", "Крок 2"],
  "goal": "Чого маємо досягти",
  "result": "Який результат нам потрібен",
  "strategy": "Назва стратегії",
  "kpi": "Метрика і поріг"
}
```

**Тригери:** `always` · `zero_revenue` · `drop` · `growth` · `cancel_rate` · `broken_utm` ·
`stale_pipeline` · `stockout` · `family_growth` · `gap_to_target` · `share_of_revenue`

**Плейсхолдери:** `{rev}` `{orders}` `{prev_rev}` `{delta}` `{aov}` `{pfull}` `{gap}`
`{cancelled}` `{cancel_rate}` `{share}` `{prev_month}` `{target}` `{forecast}` `{rem_days}`
`{gap_per_day}` `{stale_orders}` `{stale_sum}` `{stale_days}` `{close_rate}` `{family}`
`{family_delta}` `{family_rev}` `{fb_literal}` `{usd}`

## Локальний запуск

```bash
export KEYCRM_TOKEN=...
UATAC_RAW=.cache/raw.json UATAC_OUT=.out UATAC_DECISIONS=decisions.json \
UATAC_HISTORY=history.csv python3 scripts/daily_brief.py --days 130
```

`--no-fetch` — перерахувати на вже завантажених даних, без звернень до API.

База «рік до року» окремо (важка, раз на тиждень):

```bash
UATAC_BASELINE=baseline.json UATAC_BASELINE_RAW=.cache/long.json \
python3 scripts/baseline.py --days 540 --refetch
```

## Правила

- KeyCRM = **read-only**, тільки GET. Пауза 0.4 с між сторінками (ліміт ~60 запитів/хв).
- База розрахунку — **закриті угоди** (`closed_at`, `status_group_id == 5`).
  Група 6 — скасування, групи 1–4 — «в роботі».
- UAH і USD не змішувати: Shopify INTL конвертується за курсом у `analyze.py`.
- Сторінка має `noindex, nofollow` — у пошук не потрапляє. Але посилання відкриє будь-хто,
  хто його має. Якщо треба закрити наглухо — приватний репозиторій + GitHub Pages на платному
  тарифі, або окремий хостинг з паролем.

## Якщо щось зламалось

`Actions` → останній запуск → червоний крок покаже причину.

| Симптом | Причина |
|---|---|
| `НЕМАЄ KEYCRM_TOKEN` | не доданий секрет (крок 1) |
| `403` на push | не увімкнені write-права (крок 2) |
| `401` від KeyCRM | токен відкликано або протермінований |
| Сторінка стара | Pages не перебудувались — глянь вкладку `Actions` → `pages-build-deployment` |
