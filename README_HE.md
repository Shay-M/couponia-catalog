<div dir="rtl">

**עדכון נובמבר 2026 — v3.1:** התווסף מנגנון פרסום יציב שנמנע מעדכונים חוזרים כשאין שינוי, ומפריד גרסת רשימות היישום מגרסת הטבות לא מאומתות. ראו [הוראות עדכון v3.1](docs/UPDATE_v31_HE.md).

</div>

# מאגר תווי קנייה מרכזי — GitHub Actions / SQLite / JSON

**POC v3 — מבוסס על מאגר v2 שהכנו קודם.** המערכת בנויה על מקורות נפרדים, מאחדת נתונים בצורה שמרנית, ומפרידה בין שיוכים שפורסמו במאגר לבין **מועמדים לאימות** המגיעים מפרויקטים אחרים.

## מה יש בחבילה

- `seed/catalog-v2.db` — 99 כרטיסים, 409 עסקים, 504 קשרים; רשימה חלקית שתוקפה תלוי בתאריך ומקור כל קשר.
- `src/build.py` — מחולל SQLite v3 ותוצרי JSON ליישום Android.
- `.github/workflows/publish-catalog.yml` — בדיקות והפקה שבועית של JSON ו-SQLite, פרסום דרך GitHub Pages.
- `tests/` — ארבע בדיקות עם נתונים סינתטיים לבחינת שמירת בסיס הנתונים, סינון מידע ישן והגנה ממיפוי שגוי.
- `dist/v3/` — תוצר מקומי התחלתי, **ללא יבוא רשומות חיצוניות מהאינטרנט**, שכן לא הייתה רשת זמינה בזמן יצירת ZIP זה.

## מה בדקנו בפרויקטי GitHub

| פרויקט | שימוש אפשרי | החלטה |
| --- | --- | --- |
| https://github.com/eladkishon/buyme-mcp | קטלוג BUYME ALL: `data/buyme.json`, איסוף שבועי, פרטי ספקים | מתאם יבוא אופציונלי, מועמדים בלבד. לא להעתיק או לפרסם נתונים בלי בירור זכויות |
| https://github.com/yhyatt/ClawSavings | `discounts.json` — הייטקזון/פועלים Wonder/קטגוריות/מבצעים | Action מושך ציבורית ומסמן הטבות **לא מאומתות**, עם תאריך מדויק |
| https://github.com/aviv943/restaurants-il | התאמת מסעדות מ-Tabit, Ontopo, BUYME ו-HTZone | רעיון לארכיטקטורת דה-דופליקציה בלבד. README מסייג: all rights reserved |

**הפרדה עקרונית:** במקור ClawSavings שיוך של מועדון לקטגוריית אופנה **לא מוכיח** שכל חנות בקטגוריה מקבלת את הכרטיס! אנו מייבאים רק פרטי הטבות נקודתיות עם שם חנות, וגם אותן כרשומות `unverified`.

## הפעלה

```bash
python -m unittest discover -s tests -v
python src/build.py --seed seed/catalog-v2.db --out dist/v3
```

טעינה ישירה של נתוני ClawSavings (נדרש אינטרנט):

```bash
python src/build.py --seed seed/catalog-v2.db \
  --clawsavings-url https://raw.githubusercontent.com/yhyatt/ClawSavings/main/discounts.json \
  --out dist/v3
```

יבוא מקומי אופציונלי של BUYME לצורכי בדיקה — **רק לאחר בירור הרשאה לשימוש במאגר זה**:

```bash
python src/build.py --seed seed/catalog-v2.db \
  --buyme-file my-licensed-buyme.json --out dist/v3
```

היבוא מוסיף רק `acceptance_candidates`. הוא **אינו** משנה את `card_merchants`, ולכן לא יציג כיבוד כרטיס כעובדה בלי אימות.

## הפעלה ב-GitHub

1. צור Repository עצמאי והעלה את תוכן התיקייה הזו (כולל `.github`).
2. תחת Settings → Pages בחר **GitHub Actions** כמקור הפריסה.
3. פתח Actions והפעל `Build unified Israeli gift-card catalog` באמצעות `Run workflow`.
4. בסיום, הכתובת תהיה במבנה `https://USERNAME.github.io/REPO/v3/manifest.json`, וקובץ `catalog.db` באותו נתיב. הכתובת לא קיימת לפני הפרסום הראשון.

אם ה-Action נכשל במשיכה או בבדיקות, הפרסום מתבטל והגרסה הקודמת נשארת ב-Pages. GitHub מתזמן ריצות במתכונת best effort ויכול לעכב אותן.

## שימוש באפליקציית Android

- `catalog.db` כולל *תוספת* של הטבלאות `external_sources`, `benefit_candidates` ו-`acceptance_candidates`; הסכמה כעת גרסה 3.
- ב-Room יש ליצור Entities/Migration המתאימים לגרסה 3. אם אין שינוי סכמת Room כרגע, אפשר להמשיך לצרוך את ה-v2 הקיים, ובנפרד את קובצי JSON של ההטבות.
- `manifest.json` מכיל `dataVersion`, `catalogSha256`, `schemaVersion` וספירת פריטים. יש לבדוק checksum ולהחליף DB רק באופן אטומי ולא למחוק נתוני משתמש.
- יש להציג `unverified` והטבות `stale` כמידע לבדיקה, לא כתשלום ודאי בקופה. אין להסיק 'לא מכבדים' מחוסר במידע.

## מגבלות ושלבים מומלצים

- אין פה עדיין איסוף ישיר מהאתרים הרשמיים של HappyGift, תו הזהב ו-Swish. הנתונים האלה נשארו מגרסה 2.
- אין כרגע יכולת לאמת נתוני שטראוס+ אישיים מתוך חשבון של משתמש, ואין לשמור אישורי התחברות במאגר ציבורי.
- BUYME ALL הוא מוצר ספציפי; לא נכון להסיק שכל אחד מ-1,200+ העסקים במאגר צד שלישי מכבד גם כל כרטיס BUYME אחר.
- יש להוסיף מתאמים לפי מוצר כרטיס, להצליב עם רשימות המנפיקים, לתעד היתרי שימוש ולהגדיר ספי חריגה מחמירים לפני פרסום עדכון אוטומטי.

<div dir="rtl">

## התאמה ל־Couponia שלב 3

בגרסת ההפצה הנוכחית `manifest.json` מכיל `fileSha256` לשלושת קובצי הנתונים `cards.json`, `merchants.json`, `acceptance.json` ומספר `dataVersion` בפורמט זמן המאפשר עדכונים חוזרים גם באותו יום. האפליקציה דורשת את השדות האלה כדי להפעיל סנכרון מאובטח ונמנעת מעדכון אם אינם קיימים. אין להשתמש בגרסת Repo ישנה שאינה מייצרת אותם.

הקטלוג המפורסם דרך GitHub Pages זמין בדרך כלל תחת `/v3/manifest.json`, כי ה־Action מפרסם את תיקיית `dist` ומאחסן בתוכה את `v3`.

הרשאות לסקרייפינג ולהפצה מחדש הן באחריות בעל המאגר. מועמדים לא מאומתים ממועדוני הטבות **אינם** מתווספים לטבלת הקשרים המאושרים לתצוגת חנויות באפליקציה.

</div>
