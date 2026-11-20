<div dir="rtl">

# Couponia Catalog — עדכון תשתית v3.1

החבילה מיועדת ל־`Shay-M/couponia-catalog` בענף **`master`**.
אין למחוק את תיקיות `seed/` או `dist/` שכבר קיימות ב־Repository.

## מה תוקן

- ה־Action מתוזמן **מדי יום**, במקום פעם בשבוע, ומושך את `ClawSavings/discounts.json` בכל ריצה.
- **אין fallback שקט למאגר ריק**: אם המקור אינו זמין, הריצה נכשלת והאתר המפורסם נשאר עם הנתונים האחרונים התקינים.
- מחולל `release.py` משווה את התוכן לקבצים שפורסמו קודם ב־GitHub Pages.
- אם לא השתנה דבר — לא מתבצע Deploy ולא משתנה `dataVersion`.
- אם השתנו רק מועמדים להטבות — מתעדכן `enrichmentVersion`, אך `dataVersion` של Android **נשמר** כדי להימנע מהורדה חוזרת מיותרת.
- אם בעתיד ישתנו שלוש רשימות הליבה של האפליקציה — `dataVersion` תתקדם.
- מחיקה חריגה של רשימות עסקים/כרטיסים (>10%) או מועמדים להטבות (>40%) תחסום פרסום ותדרוש בדיקה ידנית.
- מצב הרשאות: `ClawSavings` כולל הצהרת MIT; `buyme-mcp` אינו מיובא אוטומטית כי לא אומתה הרשאת הפצה מחדש. מידע לא מאומת אינו מוצג ככיבוד ודאי בקופה.

## קבצים שצריך להעלות / להחליף

1. `.github/workflows/publish-catalog.yml` — **להחליף** את ה־Workflow הקיים
2. `src/build.py` — **להחליף** (ניקוי חיבורי SQLite)
3. `src/release.py` — **להוסיף** (חדש)
4. `tests/test_build.py` — **להחליף** (ניקוי משאבי בדיקה)
5. `src/watch_sources.py` — **להוסיף** (חדש, מעקב אחר שינויי המקור בלי להעתיק מידע)
6. `tests/test_release.py` — **להוסיף** (חדש)
7. `docs/UPDATE_v31_HE.md` — **להוסיף** (מסמך זה)
8. `README_HE.md` — **לעדכן** עם הפניה לתיעוד החדש

אין להעלות מחדש את `dist/` או `seed/` מתוך חבילת השינויים.

### דרך נוחה — GitHub Desktop

1. Clone של `https://github.com/Shay-M/couponia-catalog.git` לענף `master`.
2. חלץ את קובץ ה־ZIP של העדכון ישירות לתיקיית ה־Repository המקומי, תוך החלפת קבצים קיימים.
3. ב־GitHub Desktop בדוק את השינויים → Commit → Push origin.

### דרך שורת הפקודה — Windows

מתוך עותק מקומי של ה־Repository, לאחר העתקת הקבצים החדשים:

```powershell
git status
git add .github/workflows/publish-catalog.yml src/build.py src/release.py tests/test_build.py tests/test_release.py src/watch_sources.py docs/UPDATE_v31_HE.md README_HE.md
git commit -m "Make catalog publishing idempotent and fail-safe"
git push origin master
```

## בדיקת תוצאה

1. פתח `Actions` → `Build unified Israeli gift-card catalog` → `Run workflow` על הענף `master`.
2. בהרצה הראשונה על המאגר הישן צפוי `changed=true` לצורך עדכון חד־פעמי של מבנה ה־Manifest, גם אם מספר החנויות לא השתנה. `dataVersion` של האפליקציה תישאר זהה.
3. בהמשך, אם ה־Action מדפיס `changed=false`, **זה תקין** — התוכן לא השתנה ולכן אין פרסום מיותר. אם `changed=true`, הוא יפרסם עדכון ל־GitHub Pages. הקובץ יהיה בכתובת:
   `https://shay-m.github.io/couponia-catalog/v3/manifest.json`.
4. וודא שהשדות `dataVersion`, `enrichmentVersion`, `fileSha256`, `counts` מופיעים.
5. בדוק בריצה חוזרת ללא שינוי במקור שה־Deploy מדולג וש־`dataVersion` נשאר זהה.

## בדיקות מקומיות

```bash
python -m unittest discover -s tests -v
python src/build.py --seed seed/catalog-v2.db --out /tmp/couponia-test-v3
```

## מה עדיין לא מחובר?

- ה־Action מדווח בלוג על זמן ו־SHA של העדכון האחרון בקובץ BUYME הציבורי. **הוא לא מעתיק את תוכנו**.
- BUYME אינו מיובא אוטומטית אל `card_merchants`: קודם צריך לברר תנאי שימוש ולהקים מקור מאושר או מתאם למידע שמותר לפרסם. אפשרות היבוא המקומית הישנה נשארת **מועמדים לא מאומתים בלבד**.
- אין עדיין סקרייפר רשמי ל־HappyGift, Swish או תו הזהב.
- האפליקציה עצמה לא שונתה בשלב זה; החיבור שלה לכתובת ה־Manifest וממשק העדכון בהגדרות הם המשימה הבאה.

**לא להגדיר את מאות העסקים ממקור צד שלישי ככיבוד מאומת ללא הצלבה מול מוצר התו המדויק.**

</div>
